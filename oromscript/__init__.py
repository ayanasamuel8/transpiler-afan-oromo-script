"""
OromScript — Write Python in your local language.

Public API::

    from oromscript import transpile, execute

    py_src = transpile('agarsiisi("Akkam!")', lang='afan_oromo')
    execute('agarsiisi("Akkam!")', lang='afan_oromo')
"""

from __future__ import annotations

import typing
from pathlib import Path

from .adapter import AdapterRegistry
from .codegen import CodeGen
from .errors import OrmSyntaxError
from .graphemes import grapheme_len, split_graphemes
from .lexer import OrmLexer
from .parser import OrmParser
from .semantic import SemanticAnalyser

__all__ = [
    "execute",
    "grapheme_len",
    "split_graphemes",
    "transpile",
]

_ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"
if _ADAPTERS_DIR.exists():
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
    try:
        tokens = OrmLexer(source, adapter).tokenize()
        tree = OrmParser(adapter).parse(tokens)
        tree, src_map = SemanticAnalyser(source.splitlines(), strict=strict).analyse(
            tree
        )
        py_source, map_json = CodeGen().generate(
            tree, source_map=src_map if emit_map else None
        )
    except RecursionError as exc:
        # Deeply nested code (or a very long chain of operators) can exhaust
        # the stack in the visitors that walk the tree.
        raise OrmSyntaxError(
            code="E0010",
            message="The program is nested too deeply",
            lang=lang,
        ) from exc
    if emit_map:
        return py_source, map_json  # type: ignore[return-value]
    return py_source


def execute(
    source: str,
    lang: str = "afan_oromo",
    globals: dict[str, typing.Any] | None = None,
) -> None:
    """Transpile and execute localised source.

    Args:
        source:  Raw source text in the local language.
        lang:    Language adapter to use.
        globals: Optional globals dict for exec().
    """
    result = transpile(source, lang=lang)
    py_source = result[0] if isinstance(result, tuple) else result
    namespace = {} if globals is None else globals
    exec(compile(py_source, "<orm>", "exec"), namespace)  # noqa: S102
