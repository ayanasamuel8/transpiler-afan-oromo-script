# OromScript Core — Full Module Skeletons

These are the canonical source skeletons. Implement by filling in the method bodies.
All type hints, docstrings, and structural decisions here are **final** — do not deviate
without updating this file and opening a design ADR.

---

## oromscript/lexer.py

```python
"""
oromscript.lexer
~~~~~~~~~~~~~~~~
Tokenises Afan Oromo (or any localised) Python source and translates
language-specific keywords/builtins into their Python equivalents.

This is the first stage of the OromScript transpile pipeline.
"""
from __future__ import annotations

import io
import tokenize
from typing import TYPE_CHECKING

from .errors import OrmLexError

if TYPE_CHECKING:
    from .adapter import Adapter


class OrmLexer:
    """Tokenise a localised source string and translate it to Python tokens.

    Args:
        source: Raw source text in the target local language.
        adapter: The loaded Adapter for the active language.

    Example::

        lexer = OrmLexer(source, adapter)
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str, adapter: "Adapter") -> None:
        self._source = source
        self._adapter = adapter
        # Merge keyword + builtin maps once at init — O(1) lookup in hot path
        self._combined_map: dict[str, str] = {
            **adapter.keyword_map,
            **adapter.builtin_map,
        }

    def tokenize(self) -> list[tokenize.TokenInfo]:
        """Tokenise the source and return a translated token list.

        Returns:
            List of TokenInfo where local-language NAME tokens have been
            replaced with their Python equivalents.

        Raises:
            OrmLexError: If the source cannot be tokenised.
        """
        try:
            raw = list(
                tokenize.generate_tokens(io.StringIO(self._source).readline)
            )
        except tokenize.TokenizeError as exc:
            raise OrmLexError(
                code="E0001",
                message=str(exc),
                orm_line=getattr(exc, "lineno", 0),
                orm_col=getattr(exc, "offset", 0),
                lang=self._adapter.lang,
            ) from exc
        return [self._translate(tok) for tok in raw]

    def _translate(self, tok: tokenize.TokenInfo) -> tokenize.TokenInfo:
        """Translate a single token if it is a known local-language name."""
        if tok.type == tokenize.NAME:
            py_equiv = self._combined_map.get(tok.string)
            if py_equiv:
                return tok._replace(string=py_equiv)
        return tok
```

---

## oromscript/parser.py

```python
"""
oromscript.parser
~~~~~~~~~~~~~~~~~
Reconstructs Python source from translated tokens and parses it into an AST.

This is the second stage of the OromScript transpile pipeline.
"""
from __future__ import annotations

import ast
import tokenize
from typing import TYPE_CHECKING

from .errors import OrmSyntaxError

if TYPE_CHECKING:
    from .adapter import Adapter


class OrmParser:
    """Parse a translated token stream into a Python AST.

    Args:
        adapter: The loaded Adapter for the active language.
    """

    def __init__(self, adapter: "Adapter") -> None:
        self._adapter = adapter

    def parse(self, tokens: list[tokenize.TokenInfo]) -> ast.AST:
        """Convert tokens to AST.

        Args:
            tokens: Translated token list from OrmLexer.tokenize().

        Returns:
            A valid Python AST.

        Raises:
            OrmSyntaxError: If the source has a syntax error.
        """
        source = tokenize.untokenize(tokens)

        # Apply grammar hooks if the adapter supplies them
        if self._adapter.grammar_hooks is not None:
            hook = getattr(self._adapter.grammar_hooks, "pre_parse", None)
            if hook is not None:
                source = hook(source)

        try:
            return ast.parse(source, filename="<orm>", type_comments=False)
        except SyntaxError as exc:
            raise OrmSyntaxError(
                code="E0010",
                message=exc.msg,
                orm_line=exc.lineno or 0,
                orm_col=exc.offset or 0,
                lang=self._adapter.lang,
                context={"text": exc.text or ""},
            ) from exc
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
