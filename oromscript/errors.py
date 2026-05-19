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
