from __future__ import annotations

import tokenize

import pytest

from oromscript.errors import OrmLexError
from oromscript.lexer import OrmLexer


def test_translates_keyword(oromo_adapter):
    """'agarsiisi' should be translated to 'print'."""
    lexer = OrmLexer('agarsiisi("hello")', oromo_adapter)
    tokens = lexer.tokenize()
    names = [t.string for t in tokens if t.type == tokenize.NAME]
    assert "print" in names
    assert "agarsiisi" not in names


def test_untranslated_identifier_preserved(oromo_adapter):
    """User-defined identifier 'maqaa' must pass through unchanged."""
    lexer = OrmLexer("maqaa = 42", oromo_adapter)
    tokens = lexer.tokenize()
    names = [t.string for t in tokens if t.type == tokenize.NAME]
    assert "maqaa" in names


def test_preserves_string_contents(oromo_adapter):
    """Oromo words inside string literals must NOT be translated."""
    source = 'x = "agarsiisi fi hanga"'
    lexer = OrmLexer(source, oromo_adapter)
    tokens = lexer.tokenize()
    strings = [t.string for t in tokens if t.type == tokenize.STRING]
    assert '"agarsiisi fi hanga"' in strings


def test_lex_error_on_bad_char(oromo_adapter):
    """Invalid character should raise OrmLexError with code E0001."""
    with pytest.raises(OrmLexError) as exc_info:
        OrmLexer("\x00invalid", oromo_adapter).tokenize()
    assert exc_info.value.code == "E0001"


def test_token_immutability(oromo_adapter):
    """Original token list must not be mutated."""
    source = "yoo dhugaa:"
    lexer = OrmLexer(source, oromo_adapter)
    tokens_before = list(lexer._source)
    lexer.tokenize()
    assert list(lexer._source) == tokens_before


def test_lexer_token_error():
    from oromscript import transpile

    with pytest.raises(OrmLexError) as exc:
        transpile('agarsiisi("', lang="afan_oromo")
    assert exc.value.code == "E0001"
