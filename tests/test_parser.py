import ast

import pytest

from oromscript.errors import OrmSyntaxError
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser


def test_parses_hello_world(oromo_adapter):
    source = 'agarsiisi("Akkam!")'
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    tree = OrmParser(oromo_adapter).parse(tokens)
    assert isinstance(tree, ast.AST)
    # Should contain a Call node
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert len(calls) == 1


def test_syntax_error_raises_orm_error(oromo_adapter):
    source = "yoo :"   # missing condition
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    with pytest.raises(OrmSyntaxError) as exc_info:
        OrmParser(oromo_adapter).parse(tokens)
    assert exc_info.value.code == "E0010"
    assert exc_info.value.orm_line >= 1
