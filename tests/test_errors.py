from __future__ import annotations

from oromscript.errors import (
    OrmAdapterError,
    OrmError,
    OrmLexError,
    OrmNameError,
    OrmSyntaxError,
)


def test_orm_error_formatting():
    err = OrmError(code="E0001", message="Test", orm_line=1, orm_col=2)
    assert str(err) == "[E0001] line 1, col 2: Test"

def test_error_classes():
    assert issubclass(OrmLexError, OrmError)
    assert issubclass(OrmSyntaxError, OrmError)
    assert issubclass(OrmNameError, OrmError)
    assert issubclass(OrmAdapterError, OrmError)
