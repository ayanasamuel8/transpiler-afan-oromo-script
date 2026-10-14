# Architecture

The OromScript transpiler pipeline is designed to be fully standard-compliant with modern Python, meaning its output is standard Python code. The pipeline consists of the following core stages:

1. **Lexer** (`oromscript.lexer`): A hand-written lexer. It splits the source into tokens, tracks indentation, and replaces local-language names with Python names (e.g., `hojii` -> `def`).
2. **Parser** (`oromscript.parser`): A hand-written recursive descent parser. It turns the token stream into a standard Python Abstract Syntax Tree (AST).
3. **Semantic Analysis** (`oromscript.semantic`): Validates the AST and prepares source-map information.
4. **Code Generation** (`oromscript.codegen`): Traverses the AST to reconstruct perfectly formatted Python source code using `ast.unparse`.

A fifth module, `oromscript.graphemes`, holds helpers for Afan Oromo letters. The lexer uses it to accept every kind of apostrophe.

For a full breakdown of the system design, read the [OromScript Design Specification](OromScript_Design_Specification.md).

## Lexer

The lexer reads the whole source with one compiled regular expression. It does not use Python's `tokenize` module. It produces standard `tokenize.TokenInfo` objects, so other tools can read its output.

What it does:

- **Tokens.** Names, numbers (hex, octal, binary, floats, imaginary, underscores), strings (all prefixes, triple quotes, escapes), operators, and comments.
- **Layout.** It emits `NEWLINE`, `INDENT`, and `DEDENT` tokens. A tab counts as up to the next multiple of 8 columns. Blank lines and comment-only lines do not change indentation. Newlines inside brackets and after a backslash do not end a statement.
- **Translation.** A name found in the adapter's keyword or builtin map is replaced by the Python name. Names inside strings and comments are never changed.
- **Positions.** Each token keeps its line and column in the original `.orm` source, even after translation. Errors point at the original text.
- **f-strings.** Names inside the `{...}` fields of an f-string are translated. Text outside the fields and the format specifications are left alone. Strings that reuse the outer quote inside a field (Python 3.12 style) work.
- **Hudhaa.** Some Afan Oromo words contain an apostrophe, such as `walitti_ida'i`. The lexer matches these words and also accepts the curly apostrophes `’`, `ʼ`, and `‘`, because many keyboards produce them.
- **Identifiers.** Names that are not plain ASCII are normalised to NFKC form, as Python does. A character that cannot be in a name is an error.
- **Byte order mark.** A leading byte order mark (`U+FEFF`) is ignored. Python's `ast.parse` rejects it in text, but editors on Windows often add it to UTF-8 files.
- **Differences from `tokenize`.** The tokens equal `tokenize` for ordinary Python, with these exceptions: `\r\n` and lone `\r` become `\n`, a leading byte order mark is dropped, non-ASCII names are NFKC-normalised, f-strings are one `STRING` token (as `tokenize` does before Python 3.12), and an invalid number such as `0x` or `1__0` is split into separate tokens that the parser then rejects.
- **Errors.** Problems raise `OrmLexError` with code `E0001`: an unterminated string (an unterminated `"""` is never read as an empty string), a character that is not valid, a NUL byte anywhere, an unclosed bracket (the message names the bracket and points at it), an indentation level that matches no outer level, mixed tabs and spaces that Python would reject, and a backslash at the very end of the file.

Line and column numbers in lexer and parser errors both start at 1.

The lexer follows the rules of CPython's own tokenizer, including odd ones: a backslash inside the indentation fixes the indentation level, and a backslash followed by spaces at the end of the file is accepted.

## Parser

The parser is a recursive descent parser. Each grammar rule is one method. Binary operators use precedence climbing, which keeps the number of calls per expression small.

- It covers the Python grammar of the Python version that runs it: all statements, expressions, comprehensions, lambdas, decorators, `async`, `match` statements with every pattern kind, parenthesised `with` items, and, where that Python allows them, `except*`, starred subscripts, type parameters and `type` aliases. Newer syntax is rejected on older Python, as `ast.parse` does.
- `match` and `case` are soft keywords. The parser tries a `match` statement first and falls back to treating `match` as a normal name, so `match = 1` still works.
- Every node gets `lineno`, `col_offset`, `end_lineno`, and `end_col_offset`, set from the tokens. Columns count characters, not UTF-8 bytes.
- **f-strings** are cut into text and fields by `oromscript.fstrings`. Each field expression is read by the same lexer and parser. The result follows CPython's rules for the Python version that runs it: from 3.12 a field may hold the outer quote, backslashes, comments and newlines, and format specs may nest one level deeper. Every node inside an f-string carries the position of the whole string.
- Plain string literals are decoded by `oromscript.strings`, not by `ast.literal_eval`. A bad escape such as `"\d"` gives a warning that names the `.orm` line, and no global warning filter is changed, so it is safe to use from threads.
- **Speed.** The parser reuses one object for each context and operator (as CPython does), skips the `or`, `and` and comparison levels for simple operands, and pauses Python's cycle collector while it builds the tree (`oromscript._gc`).
- Code nested too deeply for the Python stack (about 70 levels of brackets, depending on the call stack) raises `OrmSyntaxError` instead of `RecursionError`.
- Errors raise `OrmSyntaxError` with code `E0010`, the line, the column, and the source text of the line.
- If an adapter's `grammar_hooks.pre_parse` changes the source text, the parser reads the changed text with Python's own `ast.parse`. Any hook makes the parser rebuild the whole source text first, which takes about 8% of the parse time, so define one only if it changes something. The Afan Oromo adapter defines none.
- Python 3.14 template strings (`t"..."`) are not supported.

## Graphemes

`oromscript.graphemes` knows how Afan Oromo (Qubee) letters are written:

| Kind | Examples |
|------|----------|
| Digraphs (`digraph`) | `ch`, `dh`, `ny`, `ph`, `sh`, `ts`, `zy` |
| Long vowels (`long_vowel`) | `aa`, `ee`, `ii`, `oo`, `uu` |
| Doubled consonants (`geminate`) | `bb`, `kk` |
| Doubled digraphs (`geminate_digraph`) | `cch`, `ddh` |
| Hudhaa (`hudhaa`) | `'`, `’`, `ʼ`, `‘` |

A unit is written in one case (`aa`, `AA`) or capitalised (`Aa`, `Ch`).

```python
from oromscript import split_graphemes, grapheme_len

split_graphemes("dhaabbata")   # ['dh', 'aa', 'bb', 'a', 't', 'a']
grapheme_len("dhaabbata")      # 6
```

### Grapheme nodes in the syntax tree

`Grapheme` is an `ast.AST` node with the fields `text`, `kind`, `start` and `end` (offsets in the name). The parser attaches a tuple of them to every `Name`, `Attribute`, `arg`, `keyword`, `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `ExceptHandler` and `alias` as the attribute `graphemes`:

```python
from oromscript.graphemes import iter_graphemes

for node, graphemes in iter_graphemes(tree):
    print(type(node).__name__, [g.text for g in graphemes if g.is_multi_character])
# arg ['dh', 'aa', 'bb']
```

`graphemes` is not one of the node's `_fields`, so `ast.walk`, `ast.dump`, `ast.unparse` and `compile` ignore it and the tree stays valid Python. Equal names share the same cached nodes, so do not change them. The nodes describe names as they stand in the tree, so a translated keyword shows its Python name (`print`, not `agarsiisi`).

## Testing

The lexer and parser are checked against Python itself:

- The parser's tree and node positions are compared with `ast.parse` on hundreds of snippets, and on a sample of the Python standard library.
- The lexer's tokens are compared with `tokenize` on plain Python source.
- Invalid programs must be rejected by both parsers.
- Memory tests (`tests/test_memory.py`) run the pipeline many times and fail if memory or object counts grow.
- Speed tests (`tests/test_performance.py`) check throughput and that time grows in line with file size.

Run everything with `make test`. Run the full standard library comparison with `pytest -m slow`. Run the benchmark with `make bench`.

## Performance

`python benchmarks/bench.py` prints the time for each stage. On a development laptop (Python 3.14), measured on two 1 MB files:

| File | Tokens | Lexer | Parser | Lexer + parser |
|------|--------|-------|--------|----------------|
| Print statements (35,000 lines) | 175,000 | 0.27 to 0.33 s | 0.25 to 0.37 s | 250,000 to 330,000 tokens/sec |
| Mixed code from `examples/` | 215,000 | 0.37 to 0.48 s | 0.30 to 0.45 s | 230,000 to 320,000 tokens/sec |

The first figure in each range is the best of several runs, and the second is the mean of three runs in `benchmarks/bench.py` on a busy desktop. The whole transpile of a 1 MB file, including semantic analysis and code generation, takes about 1.2 to 1.3 seconds. The numbers depend on the machine and vary by about 20% from run to run.
