# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Initial project scaffold for OromScript.
- `match` (`walsimsiisi`) and `case` (`haala`) keywords to Afan Oromo adapter.
- `for_loop.orm`, `if_case.orm`, and `switch.orm` examples inside the `examples/` directory.
- Populated `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.
- Comprehensive `README.md` details referencing the main architecture and features.
- Hand-written lexer (`oromscript/lexer.py`). It replaces the wrapper around Python's `tokenize` module and keeps the original line and column on every token.
- Hand-written recursive descent parser (`oromscript/parser.py`). It builds a standard Python `ast` tree directly including f-strings (in `oromscript/fstrings.py`), and `match` statements, parenthesised `with` items, `except*`, and (on Python 3.12 and newer) type parameters and `type` aliases.
- `Grapheme` nodes (`oromscript.graphemes`): `ast.AST` nodes for the digraphs, long vowels, doubled consonants and hudhaa of a name. The parser attaches them to every `Name`, `Attribute`, `arg`, `keyword`, `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, `ExceptHandler` and `alias` as `node.graphemes`. They do not change `ast.walk`, `ast.dump`, `ast.unparse` or `compile`. `iter_graphemes(tree)` finds them.
- `oromscript/fstrings.py`, a hand-written f-string parser that follows CPython's rules for each Python version (3.10 to 3.14).
- `oromscript/_gc.py`: the lexer and parser pause Python's cycle collector while they build objects (about 15% faster).
- `oromscript/strings.py`, which decodes string and bytes literals without `ast.literal_eval`. It does not touch the global warning filters, so it is safe with threads.
- `oromscript/graphemes.py` with `split_graphemes`, `grapheme_len`, and `normalize_hudhaa`. These are also exported from the `oromscript` package.
- Keywords that contain a hudhaa (apostrophe), such as `walitti_ida'i`, now work. Curly apostrophes (`’`, `ʼ`, `‘`) are accepted for them.
- Names inside the fields of f-strings are now translated on every Python version.
- Lexer errors for an unclosed bracket now name the bracket and point at it.
- Tests for graphemes, memory growth, speed, the full pipeline, and many more lexer and parser cases. The parser is compared with CPython's `ast.parse` for trees, node positions, and accept/reject decisions.
- `make bench` and `make test-slow`. The benchmark now reports time per stage, tokens per second, a 1 MB file, and memory growth.
- The lexer follows the rules of CPython's own tokenizer for mixed tabs and spaces (`TabError`), NUL bytes, NFKC identifier normalisation, and backslash line continuations (including the odd cases).
- A seeded mutation test (`tests/test_fuzz.py`) damages valid programs and checks that the lexer and parser accept or reject exactly what `ast.parse` does.

### Changed
- The parser is about 2 to 3 times faster than the first hand-written version: shared context and operator objects (as in CPython), a shorter path for simple operands, plain strings and names, native f-strings, and the collector pause.
- The Afan Oromo adapter no longer defines a `pre_parse` hook. Any hook makes the parser rebuild the whole source text first (about 8% of the parse time), so define one only if it changes something. `new-lang` now writes a docstring-only `grammar_hooks.py`.
- Line and column numbers in lexer errors now start at 1, like parser errors.
- Code that is nested too deeply raises `OrmSyntaxError` instead of `RecursionError`.
- An error at the end of the input (such as a missing block) now points at the last real line.
- A leading byte order mark is ignored.
- Invalid escape sequences in strings (such as `"\d"`) produce a warning that names the `.orm` line.
- `grammar_hooks.pre_parse` still receives the translated source text. If it changes the text, that text is parsed with Python's `ast.parse`. If it returns the text unchanged, the new parser is used.
- Documentation (architecture, design specification, README) describes the new lexer and parser and the measured speed.
- `make lint` now also checks `tests/` and runs mypy in strict mode, like CI. Line length is not enforced in `tests/`.

### Fixed
- `execute(source, globals={})` ignored an empty dictionary passed as `globals`.
- Fixed VS Code Extension syntax highlighting bugs and added missing configurations for extension package building.
