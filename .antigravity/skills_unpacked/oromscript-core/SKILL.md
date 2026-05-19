---
name: oromscript-core
description: >
  Build or modify the OromScript transpiler core engine — the pipeline that converts
  Afan Oromo (or any localised) Python source into standard Python 3 and executes it.
  Use this skill whenever the task involves: the Lexer (tokenisation, keyword translation),
  Parser (AST construction via ast.parse), Semantic Analyser (symbol table, scope analysis,
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
│  lexer.py   │  Translates local-lang tokens → Python tokens using O(1) dict lookup
└─────────────┘
      │ translated token list
      ▼
┌─────────────┐
│  2. PARSER  │  ast.parse(untokenized_source)  — zero-maintenance, CPython handles grammar
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
    def __init__(self, source: str, lang: str = "afan_oromo") -> None: ...
    def tokenize(self) -> list[tokenize.TokenInfo]: ...
    def _translate(self, tok: tokenize.TokenInfo) -> tokenize.TokenInfo: ...
```

**Rules:**
- ONLY translates `tokenize.NAME` tokens whose string value is in `adapter.keyword_map` OR `adapter.builtin_map`.
- Returns a NEW `TokenInfo` (via `tok._replace(string=py_kw)`) — never mutates input.
- Preserves all other tokens (whitespace, comments, operators) unchanged.
- Raises `OrmLexError` (see errors.py) on tokenisation failure, wrapping the original `tokenize.TokenizeError`.
- The hot path is the `_translate` loop — keep it branchless. The two maps should be merged into one `_combined_map: dict[str, str]` at `__init__` time.

### parser.py — OrmParser

```python
class OrmParser:
    def __init__(self, adapter: Adapter) -> None: ...
    def parse(self, tokens: list[tokenize.TokenInfo]) -> ast.AST: ...
```

**Rules:**
- Calls `tokenize.untokenize(tokens)` to reconstruct source, then `ast.parse()`.
- Before `untokenize`, calls `adapter.grammar_hooks.pre_parse(source_str)` if the hook exists (no-op by default).
- Wraps `SyntaxError` from `ast.parse` into `OrmSyntaxError` with localised message.
- Must NOT import lark, PLY, or any third-party parser library. CPython's parser is the only parser.

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
| Tokenise       | < 5 ms    | CPython `tokenize` (C extension)            |
| Keyword xlate  | < 1 ms    | Single dict lookup per NAME token           |
| Parse          | < 10 ms   | `ast.parse()` (C)                           |
| Semantic pass  | < 3 ms    | Single NodeVisitor pass                     |
| Code gen       | < 2 ms    | `ast.unparse()` (C)                         |
| **Total**      | **< 20 ms** | Any file, any size up to ~5k LOC          |

**Caching:** `oromscript run` writes compiled `.pyc` to `__pycache__/<stem>.<lang>.cpython-312.pyc`.
On re-run, if `.orm` mtime ≤ `.pyc` mtime, skip transpilation entirely and `exec` the `.pyc` directly.

**DO NOT** pre-optimise. Measure with `benchmarks/bench.py --ci` first. The C extension Lexer
is a v2 option — implement only if benchmarks prove it necessary.

---

## Coding Standards for Core Modules

- **Type-annotated** throughout. `mypy --strict` must pass with zero errors.
- **Zero runtime dependencies** beyond Python stdlib. No `lark`, `click`, `rich`, etc. in `lexer/parser/semantic/codegen/errors/adapter`.
- **Docstrings**: every public class and method gets a one-line summary + Args/Returns/Raises.
- **No global state** except `AdapterRegistry._adapters` (a class-level dict). All other state is instance-level.
- **Tests**: every new function needs a corresponding unit test in `tests/test_<module>.py`.

---

## Common Implementation Mistakes to Avoid

1. **Mutating TokenInfo** — always use `tok._replace(...)`, never `tok.string = ...`.
2. **Calling ast.parse on Oromo source directly** — the source must first pass through the Lexer + untokenize.
3. **Using exec() with a string** — always `exec(compile(src, filename, 'exec'), globals)` to get proper tracebacks.
4. **Storing adapter state globally** — multiple concurrent calls must be safe; AdapterRegistry is read-only after discover().
5. **Catching bare Exception** — always catch specific `OrmError` subclasses or `tokenize.TokenizeError` / `SyntaxError`.

---

## See Also

- `references/modules.md` — full annotated source skeletons for every module
- `references/keyword_map_schema.md` — JSON Schema for keyword_map.json
- `oromscript-adapter` skill — for everything about creating/validating adapters
- `oromscript-testing` skill — for writing tests for core modules
