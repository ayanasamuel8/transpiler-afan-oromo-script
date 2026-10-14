# OromScript Core — Full Module Skeletons

These are the canonical source skeletons. Implement by filling in the method bodies.
All type hints, docstrings, and structural decisions here are **final** — do not deviate
without updating this file and opening a design ADR.

---

## oromscript/lexer.py

The lexer is about 600 lines, so only its structure is shown here. Read `oromscript/lexer.py` for the code.

```python
class OrmLexer:
    def __init__(self, source: str, adapter: Adapter) -> None:
        # builds self._combined_map (local name -> python name, hudhaa normalised)
        # and self._scanner = _build_scanner(<keys that contain a hudhaa>)
    def tokenize(self) -> list[tokenize.TokenInfo]: ...      # public
    def _handle_indent(...) -> tuple[int, int, int, bool]    # INDENT/DEDENT, blank lines
    def _finish(...) -> list[tokenize.TokenInfo]             # NEWLINE, DEDENTs, ENDMARKER
    def _scan_fstring(...) -> tuple[int, str]                # f-string with translated fields
    def _scan_field / _scan_word / _skip_plain_string        # f-string helpers

@functools.lru_cache(maxsize=32)
def _build_scanner(apostrophe_words: tuple[str, ...]) -> re.Pattern[str]: ...
```

Master pattern groups, in order: `ws`, `comment`, `newline`, `cont`, `string`, `number`, `hudhaa`, `name`, `op`.

---

## oromscript/parser.py

The parser is about 1,600 lines, so only its structure is shown here. Read `oromscript/parser.py` for the code.

```python
class _Parser:
    # token helpers: _advance, _peek, _is_op, _is_kw, _accept_*, _expect_*, _error, _at
    def parse_module(self) -> ast.Module
    # statements: _statement, _block, _simple_stmts, _simple_stmt, _expr_or_assign,
    #   _if_stmt, _while_stmt, _for_stmt, _try_stmt, _with_stmt, _funcdef, _classdef,
    #   _decorated, _async_stmt, _import_stmt, _from_stmt, _del_stmt, _raise_stmt
    # match: _try_match_stmt (with backtracking), _patterns, _closed_pattern, ...
    # 3.12+: _type_params, _type_alias
    # f-strings: _fstring, _fstring_expression (calls fstrings.build_joined_str)
    # expressions: _star_expressions, _named_expression, _expression, _disjunction,
    #   _conjunction, _inversion, _comparison, _binary (precedence climbing),
    #   _unary, _power, _primary, _atom, _strings, _fstring, comprehensions

class OrmParser:
    def __init__(self, adapter: Adapter) -> None: ...
    def parse(self, tokens: list[tokenize.TokenInfo]) -> ast.AST: ...
```

---

## oromscript/fstrings.py

```python
class FStringError(ValueError): ...
def build_joined_str(tokens: list[tuple[str, int]], parse_expression) -> ast.JoinedStr: ...
class _Scanner:  # text_and_fields, field, expression_end, is_debug_marker, ...
```

---

## oromscript/strings.py

```python
def split_literal(text: str) -> tuple[str, str]: ...      # prefix, body
def decode_string_literal(text: str, lineno: int) -> str | bytes: ...
```

---

## oromscript/_gc.py

```python
@contextlib.contextmanager
def gc_paused() -> Iterator[None]: ...   # cycle collector off inside the block
```

---

## oromscript/graphemes.py

```python
HUDHAA = "'"
HUDHAA_VARIANTS = "'\u2019\u02bc\u2018"

class Grapheme(ast.AST):  # _fields = ("text", "kind", "start", "end")
    is_multi_character: bool
def normalize_hudhaa(text: str) -> str: ...
def grapheme_nodes(word: str) -> tuple[Grapheme, ...]: ...   # cached
def iter_graphemes(tree: ast.AST) -> Iterator[tuple[ast.AST, tuple[Grapheme, ...]]]: ...
def split_graphemes(word: str) -> list[str]: ...
def grapheme_len(word: str) -> int: ...
```

---

## oromscript/semantic.py

```python
"""
oromscript.semantic
~~~~~~~~~~~~~~~~~~~
Single-pass AST visitor that builds a symbol table and annotates nodes
with original source-map information.

This is the third stage of the OromScript transpile pipeline.
"""
from __future__ import annotations

import ast
from collections import ChainMap

# Type alias: generated-py-line → orm-line
SourceMap = dict[int, int]


class _Scope(ChainMap):
    """Nested symbol table using ChainMap for O(1) push/pop."""


class SemanticAnalyser(ast.NodeVisitor):
    """Analyse and annotate an AST.

    Args:
        source_lines: Original .orm source split by line (for error context).
        strict: If True, raise OrmNameError on undefined name references.
    """

    def __init__(self, source_lines: list[str], strict: bool = False) -> None:
        self._lines = source_lines
        self._strict = strict
        self._scope: _Scope = _Scope()
        self._orm_line_map: dict[int, int] = {}   # ast node id → orm_line

    def analyse(self, tree: ast.AST) -> tuple[ast.AST, SourceMap]:
        """Run analysis pass.

        Returns:
            (annotated_tree, source_map) where source_map maps
            each AST node's lineno to the original orm line number.
        """
        self.visit(tree)
        return tree, self._orm_line_map

    # ── Visitors ──────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope[node.name] = "function"
        self._scope = self._scope.new_child()
        for arg in node.args.args:
            self._scope[arg.arg] = "arg"
        self.generic_visit(node)
        self._scope = self._scope.parents

    visit_AsyncFunctionDef = visit_FunctionDef   # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope[node.name] = "class"
        self._scope = self._scope.new_child()
        self.generic_visit(node)
        self._scope = self._scope.parents

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._scope[target.id] = "var"
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self._strict and isinstance(node.ctx, ast.Load):
            if node.id not in self._scope and node.id not in dir(__builtins__):
                from .errors import OrmNameError
                raise OrmNameError(
                    code="E0020",
                    message=f"Name '{node.id}' is not defined",
                    orm_line=getattr(node, "lineno", 0),
                    orm_col=getattr(node, "col_offset", 0),
                    lang="",
                    context={"name": node.id},
                )
```

---

## oromscript/codegen.py

```python
"""
oromscript.codegen
~~~~~~~~~~~~~~~~~~
Generates Python source from an annotated AST using ast.unparse().

This is the fourth (and final source-emitting) stage of the pipeline.
"""
from __future__ import annotations

import ast
import json

from .semantic import SourceMap


class CodeGen:
    """Generate Python source code from an AST."""

    def generate(
        self,
        tree: ast.AST,
        source_map: SourceMap | None = None,
    ) -> tuple[str, str | None]:
        """Generate Python source and optionally a source-map JSON.

        Args:
            tree: Annotated AST from SemanticAnalyser.
            source_map: Optional line mapping (orm_line → py_line).

        Returns:
            (py_source, map_json_or_None)
        """
        py_source = ast.unparse(tree)
        # Normalise: re-parse and re-unparse for deterministic whitespace
        py_source = ast.unparse(ast.parse(py_source))

        map_json: str | None = None
        if source_map is not None:
            map_json = json.dumps(
                {"version": 1, "mappings": source_map},
                ensure_ascii=False,
                indent=2,
            )
        return py_source, map_json
```

---

## oromscript/errors.py

```python
"""
oromscript.errors
~~~~~~~~~~~~~~~~~
Structured error types for all pipeline stages.
Error messages are localised via the active adapter's error_messages.json.
"""
from __future__ import annotations


class OrmError(Exception):
    """Base class for all OromScript errors."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        orm_line: int = 0,
        orm_col: int = 0,
        lang: str = "afan_oromo",
        context: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.orm_line = orm_line
        self.orm_col = orm_col
        self.lang = lang
        self.context = context or {}
        super().__init__(self._format())

    def _format(self) -> str:
        loc = f"line {self.orm_line}, col {self.orm_col}"
        return f"[{self.code}] {loc}: {self.message}"


class OrmLexError(OrmError):
    """Raised when the source cannot be tokenised."""


class OrmSyntaxError(OrmError):
    """Raised when the translated source fails ast.parse()."""


class OrmNameError(OrmError):
    """Raised in strict mode when a name is undefined."""


class OrmAdapterError(OrmError):
    """Raised when an adapter cannot be found or loaded."""
```

---

## oromscript/adapter.py

```python
"""
oromscript.adapter
~~~~~~~~~~~~~~~~~~
Adapter data class and registry.

An Adapter encapsulates all language-specific data (keyword maps,
error messages, optional grammar hooks) for one local language.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .errors import OrmAdapterError


@dataclass
class Adapter:
    lang: str
    keyword_map: dict[str, str]
    builtin_map: dict[str, str]
    error_messages: dict[str, str]
    grammar_hooks: ModuleType | None = field(default=None, repr=False)

    @classmethod
    def load(cls, adapter_dir: Path) -> "Adapter":
        """Load an adapter from a directory.

        Args:
            adapter_dir: Path to the adapter folder (must contain keyword_map.json).

        Raises:
            OrmAdapterError: If keyword_map.json is missing or malformed.
        """
        kmap_path = adapter_dir / "keyword_map.json"
        if not kmap_path.exists():
            raise OrmAdapterError(
                code="E0050",
                message=f"keyword_map.json not found in {adapter_dir}",
                lang=adapter_dir.name,
            )
        raw = json.loads(kmap_path.read_text(encoding="utf-8"))
        lang = raw.get("$lang", adapter_dir.name)

        # Load optional error messages
        err_path = adapter_dir / "error_messages.json"
        error_messages: dict[str, str] = {}
        if err_path.exists():
            error_messages = json.loads(err_path.read_text(encoding="utf-8"))

        # Load optional grammar hooks module
        hooks: ModuleType | None = None
        try:
            hooks = importlib.import_module(
                f"adapters.{adapter_dir.name}.grammar_hooks"
            )
        except ModuleNotFoundError:
            pass

        return cls(
            lang=lang,
            keyword_map=raw.get("keywords", {}),
            builtin_map=raw.get("builtins", {}),
            error_messages=error_messages,
            grammar_hooks=hooks,
        )


class AdapterRegistry:
    """Global registry of available language adapters."""

    _adapters: dict[str, Adapter] = {}

    @classmethod
    def discover(cls, adapters_dir: Path) -> None:
        """Scan adapters_dir and register all found adapters."""
        for d in adapters_dir.iterdir():
            if d.is_dir() and (d / "keyword_map.json").exists():
                if d.name not in cls._adapters:
                    cls._adapters[d.name] = Adapter.load(d)

    @classmethod
    def get(cls, lang: str) -> Adapter:
        if lang not in cls._adapters:
            raise OrmAdapterError(
                code="E0051",
                message=f"No adapter found for language '{lang}'. "
                        f"Available: {list(cls._adapters)}",
                lang=lang,
            )
        return cls._adapters[lang]

    @classmethod
    def list_langs(cls) -> list[str]:
        return sorted(cls._adapters.keys())
```

---

## oromscript/__init__.py

```python
"""
OromScript — Write Python in your local language.

Public API::

    from oromscript import transpile, execute

    py_src = transpile('agarsiisi("Akkam!")', lang='afan_oromo')
    execute('agarsiisi("Akkam!")', lang='afan_oromo')
"""
from __future__ import annotations

from pathlib import Path

from .adapter import AdapterRegistry
from .codegen import CodeGen
from .graphemes import grapheme_len, split_graphemes
from .lexer import OrmLexer
from .parser import OrmParser
from .semantic import SemanticAnalyser

_ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"
AdapterRegistry.discover(_ADAPTERS_DIR)


def transpile(
    source: str,
    lang: str = "afan_oromo",
    strict: bool = False,
    emit_map: bool = False,
) -> str | tuple[str, str]:
    """Transpile localised source to Python source.

    Args:
        source:    Raw source text in the local language.
        lang:      Language adapter to use (default: 'afan_oromo').
        strict:    Enable strict name checking.
        emit_map:  If True, also return source-map JSON.

    Returns:
        py_source if emit_map is False, else (py_source, map_json).
    """
    adapter = AdapterRegistry.get(lang)
    tokens  = OrmLexer(source, adapter).tokenize()
    tree    = OrmParser(adapter).parse(tokens)
    tree, src_map = SemanticAnalyser(
        source.splitlines(), strict=strict
    ).analyse(tree)
    py_source, map_json = CodeGen().generate(
        tree, source_map=src_map if emit_map else None
    )
    if emit_map:
        return py_source, map_json  # type: ignore[return-value]
    return py_source


def execute(
    source: str,
    lang: str = "afan_oromo",
    globals: dict | None = None,
) -> None:
    """Transpile and execute localised source.

    Args:
        source:  Raw source text in the local language.
        lang:    Language adapter to use.
        globals: Optional globals dict for exec().
    """
    py_source = transpile(source, lang=lang)
    exec(compile(py_source, "<orm>", "exec"), globals or {})  # noqa: S102
```
