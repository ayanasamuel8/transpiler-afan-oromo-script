"""
oromscript.lexer
~~~~~~~~~~~~~~~~
Tokenises Afan Oromo (or any localised) Python source and translates
language-specific keywords/builtins into their Python equivalents.

This is the first stage of the OromScript transpile pipeline.
"""

from __future__ import annotations

import io
import tokenize as py_tokenize
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

    def __init__(self, source: str, adapter: Adapter) -> None:
        self._source = source
        self._adapter = adapter
        forward_map = {
            **adapter.keyword_map,
            **adapter.builtin_map,
        }
        self._combined_map: dict[str, str] = {v: k for k, v in forward_map.items()}

    def tokenize(self) -> list[py_tokenize.TokenInfo]:
        """Tokenise the source and return a translated token list.

        Returns:
            List of TokenInfo where local-language NAME tokens have been
            replaced with their Python equivalents.

        Raises:
            OrmLexError: If the source cannot be tokenised.
        """
        try:
            raw = list(py_tokenize.generate_tokens(io.StringIO(self._source).readline))
        except py_tokenize.TokenError as exc:
            raise OrmLexError(
                code="E0001",
                message=str(exc),
                orm_line=getattr(exc, "lineno", 0),
                orm_col=getattr(exc, "offset", 0),
                lang=self._adapter.lang,
            ) from exc
        return [self._translate(tok) for tok in raw]

    def _translate(self, tok: py_tokenize.TokenInfo) -> py_tokenize.TokenInfo:
        """Translate a single token if it is a known local-language name."""
        if tok.type == py_tokenize.ERRORTOKEN:
            raise OrmLexError(
                code="E0001",
                message=f"Lexer error: {tok.string!r}",
                orm_line=tok.start[0],
                orm_col=tok.start[1],
                lang=self._adapter.lang,
            )
        if tok.type == py_tokenize.NAME:
            py_equiv = self._combined_map.get(tok.string)
            if py_equiv:
                return tok._replace(string=py_equiv)
        return tok
