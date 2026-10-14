---
name: oromscript-core
description: >
  Build or modify the OromScript transpiler core engine — the pipeline that converts
  Afan Oromo (or any localised) Python source into standard Python 3 and executes it.
  Use this skill whenever the task involves: the Lexer (tokenisation, keyword translation),
  Parser (hand-written recursive descent parser that builds the AST), Semantic Analyser (symbol table, scope analysis,
  source-map annotation), Code Generator (ast.unparse, .orm.map emission), Error Reporter
  (structured errors, localised messages), AdapterRegistry (discovering and loading language
  adapters), or the Library API (transpile()/execute() public surface).
  Also use it when wiring these components together, debugging transpile failures, or
  reviewing performance of the transpile pipeline. This skill must be consulted before
  writing any file under oromscript/ (the core library package).
---

# OromScript Core Engine

## Architecture Recap

The pipeline has **5 sequential stages**. Each stage is a separate Python module.
Data flows in one direction; no stage reaches back to a previous one.

```
.orm source str
      │
      ▼
┌─────────────┐  keyword_map.json
│  1. LEXER   │◄──────────────────── AdapterRegistry
│  lexer.py   │  Hand-written regex lexer; translates local-lang names → Python names
└─────────────┘
      │ translated token list
      ▼
┌─────────────┐
│  2. PARSER  │  hand-written recursive descent parser → standard Python ast tree
│  parser.py  │  adapter grammar_hooks.py pre-processes source string if provided
└─────────────┘
      │ ast.AST tree
      ▼
┌──────────────┐
│  3. SEMANTIC │  Single-pass NodeVisitor:
│  semantic.py │   • builds symbol table (scoped dict name→type_hint)
│              │   • validates references in --strict mode
│              │   • annotates each node with orm_line / orm_col
└──────────────┘
      │ annotated ast.AST
      ▼
┌─────────────┐
│  4. CODEGEN │  ast.unparse(tree) → py_source str
│  codegen.py │  emits .orm.map JSON (line mapping) when --map flag active
└─────────────┘
      │ py_source str
      ▼
┌─────────────┐
│  5. EXECUTE │  exec(compile(py_source, filename, 'exec'), globals())
│  (in cli.py)│  OR write .py file for --emit-python
└─────────────┘
```

---

## Module Reference

Read `references/modules.md` for the **full annotated source** of every module.
Below is the contract each module must satisfy.

### lexer.py — OrmLexer

```python
class OrmLexer:
    def __init__(self, source: str, adapter: Adapter) -> None: ...
    def tokenize(self) -> list[tokenize.TokenInfo]: ...
```

**Rules:**
- Hand-written. One compiled regular expression (`_build_scanner`, cached per set of hudhaa keywords) matches every token. It does NOT call `tokenize.generate_tokens`.
- Emits standard `tokenize.TokenInfo` objects (NAME, NUMBER, STRING, OP, COMMENT, NL, NEWLINE, INDENT, DEDENT, ENDMARKER) that match what `tokenize` produces for plain Python.
- Tracks indentation itself (tab = next multiple of 8, blank and comment-only lines are ignored, a backslash at the start of a line counts as indentation).
- Translates ONLY NAME tokens found in `adapter.keyword_map` or `adapter.builtin_map`, through one merged `_combined_map` built at `__init__`. Never translates inside strings or comments.
- Token positions are positions in the ORIGINAL source, even when the translated text has a different length.
- Keywords that contain a hudhaa (apostrophe) get their own alternative in the scanner. Curly apostrophes are normalised with `graphemes.normalize_hudhaa`.
- f-strings are scanned by hand (`_scan_fstring`) so names in `{...}` fields are translated and same-quote nesting (Python 3.12 style) works. Literal text and format specs are left alone.
- Each token's `line` attribute must come from the precomputed `line_texts` list. Never build it with `lines[i] + "\n"` per token, because that is quadratic on long lines.
- Follows CPython's tokenizer, including odd rules: tab = next multiple of 8 with a second count (tab = 1) that must agree (`TabError`), a backslash inside the indentation fixes the level at its column, a NUL byte anywhere is an error, non-ASCII names are NFKC-normalised, and a leading BOM is ignored.
- Raises `OrmLexError` with code `E0001`: unterminated string (never read an unterminated `"""` as `""` plus a string), invalid character, NUL byte, unclosed bracket (points at the bracket), bad dedent, mixed tabs and spaces, backslash at the very end of the file.

### parser.py — OrmParser

```python
class OrmParser:
    def __init__(self, adapter: Adapter) -> None: ...
    def parse(self, tokens: list[tokenize.TokenInfo]) -> ast.AST: ...
```

**Rules:**
- `OrmParser.parse` runs a hand-written recursive descent parser (`_Parser`, one method per grammar rule, precedence climbing for binary operators). It does NOT call `ast.parse` on the normal path.
- The tree must be identical to `ast.parse` for the same source: same node types, fields, and (outside f-strings) `lineno`/`col_offset`/`end_lineno`/`end_col_offset`. Set EVERY field of a node explicitly, because Python 3.10 to 3.12 do not default missing fields.
- Version-dependent syntax (`except*`, type parameters, `type` aliases, type parameter defaults, bare `except A, B:`) is gated on the running Python version.
- `match` and `case` are soft keywords: try the `match` statement, and on failure restore the position and parse a normal expression.
- f-strings are read natively: `_fstring` gives the string tokens to `fstrings.build_joined_str`, which cuts them into text and fields and calls back `_fstring_expression` (the same lexer and `_Parser`) for each field. Every node of the result gets the position of the whole literal. The rules follow CPython per version (3.12 PEP 701 changes, nesting depth, `u` kind, raw format specs). Check any change with `tests/test_fstrings.py` and the f-string fuzz in `tests/test_fuzz.py`.
- If the adapter defines `grammar_hooks.pre_parse(source)` and it returns changed text, that text is parsed with `ast.parse`. If it returns the text unchanged, the hand-written parser is used. Any hook costs a full `untokenize`, so the Afan Oromo adapter defines none.
- Share `_LOAD`/`_STORE`/`_DEL` and the operator objects (`_BINARY_OPS`, ...), as CPython does. Keep the short path in `_expression` (`_STOP_OPS`) and the inlined name in `_primary`; they are what makes the parser fast.
- `OrmParser.parse` and `OrmLexer.tokenize` run inside `_gc.gc_paused()`.
- Attach `graphemes` with `_name`, `_attribute` and `_with_graphemes` when you create a named node.
- Raises `OrmSyntaxError` with code `E0010`, with line, column (both start at 1), and the source line in `context["text"]`. An error at the end of the input points at the last real line. `RecursionError` from deep nesting becomes `OrmSyntaxError`.
- Must NOT import lark, PLY, or any third-party parser library.

### fstrings.py

`build_joined_str(tokens, parse_expression)` returns the `JoinedStr` for strings next to each other where at least one is an f-string. It raises `FStringError` (a `ValueError`) for invalid input. Version rules live at the top of the file (`_PEP_701`, `_MAX_NESTING`, `_DECODE_RAW_SPEC`, `_U_KIND_ANYWHERE`).

### strings.py

`decode_string_literal(text, lineno)` turns one non-f string token into its value. It replaces `ast.literal_eval`, which re-parses the text, reports warnings at `<unknown>`, and needs `warnings.catch_warnings` (not thread-safe). Invalid escapes warn through `warnings.warn_explicit` at `<orm>:<line>`. It is checked against `ast.literal_eval` on random literals in `tests/test_strings.py`.

### graphemes.py

Helpers for Afan Oromo letters: `grapheme_nodes(word)` (cached tuple of `Grapheme` `ast.AST` nodes with `text`, `kind`, `start`, `end`), `iter_graphemes(tree)`, `split_graphemes(word)`, `grapheme_len(word)`, `normalize_hudhaa(text)`. The parser attaches the nodes to named nodes as `node.graphemes`; this is not an `_fields` entry, so `compile` ignores it. Digraphs (`ch dh ny ph sh ts zy`), long vowels, doubled consonants and doubled digraphs, and the hudhaa count as one unit. `split_graphemes` and `grapheme_len` are public in `oromscript/__init__.py`.

### semantic.py — SemanticAnalyser

```python
class SemanticAnalyser(ast.NodeVisitor):
    def __init__(self, source_lines: list[str], strict: bool = False) -> None: ...
    def analyse(self, tree: ast.AST) -> tuple[ast.AST, SourceMap]: ...
```

**Rules:**
- `analyse()` calls `self.visit(tree)` and returns the same (mutated) tree plus the built `SourceMap`.
- `SourceMap` is `dict[int, int]` mapping generated-line-number → orm-line-number (built in `codegen.py` after `ast.unparse` runs; semantic only annotates nodes with `orm_line` attribute).
- Strict mode: raises `OrmNameError` for any `ast.Name` load not found in the current scope.
- Does NOT type-check — it reads `ast.AnnAssign` annotation strings but does not evaluate them.

### codegen.py — CodeGen

```python
class CodeGen:
    def generate(
        self,
        tree: ast.AST,
        source_map: SourceMap | None = None,
    ) -> tuple[str, str | None]:
        """Returns (py_source, map_json_or_None)."""
```

**Rules:**
- `py_source = ast.unparse(tree)` — this is the ONLY code generation step. No custom emitter.
- Map JSON is only built when `source_map is not None`. Format: `{"version":1,"mappings":{...}}`.
- Re-formats `py_source` through `ast.parse` + `ast.unparse` once more to normalise whitespace (this keeps generated output deterministic regardless of minor AST differences).

### errors.py — Error hierarchy

```python
class OrmError(Exception):
    code: str          # e.g. "E0042"
    orm_line: int
    orm_col: int
    context: dict      # substitution variables for message template
    lang: str          # active adapter language

class OrmLexError(OrmError): ...
class OrmSyntaxError(OrmError): ...
class OrmNameError(OrmError): ...
class OrmAdapterError(OrmError): ...
```

The `__str__` method delegates to `ErrorRenderer(lang).render(self)`.

### adapter.py — Adapter & AdapterRegistry

```python
@dataclass
class Adapter:
    lang: str
    keyword_map: dict[str, str]     # local_keyword → python_keyword
    builtin_map: dict[str, str]     # local_builtin  → python_builtin
    error_messages: dict[str, str]  # error_code     → message template
    grammar_hooks: ModuleType | None

class AdapterRegistry:
    @classmethod
    def discover(cls, adapters_dir: Path) -> None: ...
    @classmethod
    def get(cls, lang: str) -> Adapter: ...
    @classmethod
    def list_langs(cls) -> list[str]: ...
```

**Discovery rules:**
1. Scan `adapters/` for subdirectories containing `keyword_map.json`.
2. Also scan installed packages with entry point group `oromscript.adapters` (allows `pip install oromscript-lang-amharic`).
3. `discover()` is idempotent — calling it twice doesn't double-register.
4. `grammar_hooks` is loaded via `importlib.import_module(f"adapters.{lang}.grammar_hooks")` — if the module doesn't exist, `grammar_hooks` is `None` (not an error).

---

## Library API (public surface — __init__.py)

```python
def transpile(
    source: str,
    lang: str = "afan_oromo",
    strict: bool = False,
    emit_map: bool = False,
) -> str | tuple[str, str]:
    """
    Transpile Oromo (or other lang) source to Python source.
    Returns py_source, or (py_source, map_json) if emit_map=True.
    """

def execute(
    source: str,
    lang: str = "afan_oromo",
    globals: dict | None = None,
) -> None:
    """Transpile and exec() the source in the given globals namespace."""
```

These are the **only** public symbols in `__init__.py`. Everything else is internal.

---

## Performance Budget

| Stage          | Target    | Method                                     |
|----------------|-----------|---------------------------------------------|
| Tokenise + xlate | ~7 ms   | Hand-written regex lexer, one dict lookup per NAME |
| Parse          | ~7 ms     | Hand-written recursive descent parser       |
| Semantic pass  | ~2 ms     | Single NodeVisitor pass                     |
| Code gen       | ~11 ms    | `ast.unparse()` (C)                         |
| **Total**      | **< 100 ms** | 1000-line file (CI budget). ~1.2 s for 1 MB |

Numbers are for a 1000-line file on a development laptop. CI also requires at least 15,000 tokens per second and no memory growth.

**Caching:** `oromscript run` writes compiled `.pyc` to `__pycache__/<stem>.<lang>.cpython-312.pyc`.
On re-run, if `.orm` mtime ≤ `.pyc` mtime, skip transpilation entirely and `exec` the `.pyc` directly.

**DO NOT** pre-optimise. Measure with `benchmarks/bench.py --ci` first. The C extension Lexer
is a v2 option — implement only if benchmarks prove it necessary.

---

## Coding Standards for Core Modules

- **Type-annotated** throughout. `mypy --strict` must pass with zero errors.
- **Zero runtime dependencies** beyond Python stdlib. No `lark`, `click`, `rich`, etc. in `lexer/parser/graphemes/semantic/codegen/errors/adapter`.
- **Docstrings**: every public class and method gets a one-line summary + Args/Returns/Raises.
- **No global state** except `AdapterRegistry._adapters` (a class-level dict). All other state is instance-level.
- **Tests**: every new function needs a corresponding unit test in `tests/test_<module>.py`.

---

## Common Implementation Mistakes to Avoid

1. **Mutating TokenInfo** — it is a named tuple; build a new one instead.
6. **Leaving a node field unset** — older Pythons do not fill defaults, so `ast.unparse` or `compile` fails there.
2. **Calling ast.parse on Oromo source directly** — the source must first pass through the Lexer.
3. **Using exec() with a string** — always `exec(compile(src, filename, 'exec'), globals)` to get proper tracebacks.
4. **Storing adapter state globally** — multiple concurrent calls must be safe; AdapterRegistry is read-only after discover().
5. **Catching bare Exception** — always catch specific `OrmError` subclasses.

---

## See Also

- `references/modules.md` — full annotated source skeletons for every module
- `references/keyword_map_schema.md` — JSON Schema for keyword_map.json
- `oromscript-adapter` skill — for everything about creating/validating adapters
- `oromscript-testing` skill — for writing tests for core modules
