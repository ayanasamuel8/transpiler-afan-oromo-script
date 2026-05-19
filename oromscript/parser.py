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
