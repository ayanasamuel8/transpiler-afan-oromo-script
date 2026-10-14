"""Tests for the f-string parser (oromscript.fstrings and the parser around it)."""

from __future__ import annotations

import ast
import sys
import warnings

import pytest

from oromscript.errors import OrmError, OrmSyntaxError
from oromscript.fstrings import FStringError, build_joined_str
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser

PEP_701 = sys.version_info >= (3, 12)


def parse_with(source, adapter):
    return OrmParser(adapter).parse(OrmLexer(source, adapter).tokenize())


def python_accepts(source: str) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    return True


def assert_same(source, adapter):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = ast.parse(source)
        got = parse_with(source, adapter)
    assert ast.dump(got) == ast.dump(expected)


VALID = [
    "f''",
    'f""',
    "f'abc'",
    "f'{x}'",
    "f'a{x}b'",
    "f'{x}{y}'",
    "f'{x} {y}'",
    "f'{ x }'",
    "f'{x.y}'",
    "f'{x.y.z}'",
    "f'{x[0]}'",
    "f'{x[1:2]}'",
    "f'{x(1)}'",
    "f'{x + 1}'",
    "f'{x if y else z}'",
    "f'{not x}'",
    "f'{x and y}'",
    "f'{-x}'",
    "f'{x ** 2}'",
    "f'{(x := 1)}'",
    "f'{[i for i in x]}'",
    "f'{ {1: 2}[1] }'",
    "f'{ {1, 2} }'",
    "f'{(lambda: 1)()}'",
    "f'{x, y}'",
    "f'{x,}'",
    "f'{*a, b}'",
    "f'{yield_}'",
    "f'{await_}'",
    "f'{(yield)}'",
    "f'{yield}'",
    "f'{yield x}'",
    "f'{yield from y}'",
    "f'{x!r}'",
    "f'{x!s}'",
    "f'{x!a}'",
    "f'{x !r}'",
    "f'{x!r:>10}'",
    "f'{x:>10}'",
    "f'{x:}'",
    "f'{x:010}'",
    "f'{x:%Y-%m-%d}'",
    "f'{x:{w}}'",
    "f'{x:{w}.{p}}'",
    "f'{x:>{w}}'",
    "f'{x:a{w}b}'",
    "f'{x:{w}{p}}'",
    "f'{x:{w!r}}'",
    "f'{x:{w=}}'",
    "f'{x=}'",
    "f'{x = }'",
    "f'{ x = }'",
    "f'{x=!r}'",
    "f'{x=!s}'",
    "f'{x=:>5}'",
    "f'{x=!s:>5}'",
    "f'{x + 1=}'",
    "f'{x==y}'",
    "f'{x!=y}'",
    "f'{x<=y}'",
    "f'{x>=y}'",
    "f'{x<y}'",
    "f'{x==y=}'",
    "f'{{'",
    "f'}}'",
    "f'{{}}'",
    "f'{{{x}}}'",
    "f'{{x}}'",
    "f'a{{b}}c{x}d'",
    "f'{x}}}'",
    "f'{{{x}'",
    "f'\\n{x}'",
    "f'{x}\\n'",
    "f'\\\\{x}'",
    "f'\\x41{x}'",
    "f'\\u00e9{x}'",
    "f'\\N{BULLET}{x}'",
    "f'{x}\\N{BULLET}'",
    "f'\\{x}'",
    "f'é{x}ሰ'",
    "f'''a\nb{x}\nc'''",
    'f"""{x}"""',
    "f'''{x}'''",
    "f'''{\nx\n}'''",
    "f\"{'a'}\"",
    "f'{\"a\"}'",
    "f\"{x['k']}\"",
    "f'{x[\"k\"]}'",
    "f'{\"{\"}'",
    "f'{\"}\"}'",
    'f\'{"a" "b"}\'',
    "f'{f\"{x}\"}'",
    "f\"{f'{x}'}\"",
    "f'{x}' 'abc'",
    "'abc' f'{x}'",
    "f'a' 'b'",
    "'a' f'b'",
    "f'{x}' f'{y}'",
    "f'a' f'b' f'c'",
    "'a' 'b' f'{x}' 'c' 'd'",
    "f'a' f'{x}' f'b'",
    "f'{x}' '{y}'",
    "'{y}' f'{x}'",
    "u'a' f'{x}'",
    "f'{x}' u'a'",
    "u'a' f'b'",
    "f'a' u'b'",
    "'a' u'b' f'{x}'",
    "u'a' u'b' f'{x}'",
    "F'{x}'",
    "rf'{x}'",
    "fr'{x}'",
    "Rf'{x}'",
    "fR'{x}'",
    "RF'{x}'",
    "rf'\\n{x}'",
    "rf'\\d{x}'",
    "fr'\\{x}'",
    "rf'{x:\\n}'",
    "f'{x:\\n}'",
    "f'{x:\\x41}'",
    "f'''{x\n:>10}'''",
    "f'{x\n}'" if PEP_701 else "f'''{x\n}'''",
    "f'{x # c\n}'" if PEP_701 else "f'''{x\n}'''",
    "f'{x:{y:{z}}}'" if PEP_701 else "f'{x:{y}}'",
    "f'{x!r }'" if PEP_701 else "f'{x!r}'",
    "f'{x:{y}{{}'" if PEP_701 else "f'{x:{y}}'",
    "f'{x:{{y}}}'",
    "f'{x:{{b}}c}'",
    "f'{x:a{{b}}c}'",
    "f'{x:{y}a{{}'" if PEP_701 else "f'{x:{y}a}'",
    "f'{x:{y}{{{b}}}}'" if PEP_701 else "f'{x:{y}}'",
    "f'{f(a, b)}'",
    "f'{f(a=1)}'",
    "f'{f(*a, **k)}'",
    "f'{x:{f(a)}}'",
    "f'{x[{1: 2}[1]]}'",
    "f'{x}' if y else 'z'",
    "[f'{x}', f'{y}']",
    "{f'{k}': f'{v}'}",
    "f'{x}'.upper()",
    "f'{x}'[0]",
    "f'{x}' + f'{y}'",
    "f'{x}' % y",
    "f'{x}' in y",
    "f(f'{x}')",
    "lambda: f'{x}'",
    "(f'{x}' for x in y)",
    "f'{x}' 'a' if y else f'{z}'",
]


@pytest.mark.parametrize("literal", VALID, ids=[repr(v)[:50] for v in VALID])
def test_matches_python(literal, plain_adapter):
    assert_same(f"x = {literal}\n", plain_adapter)


INVALID = [
    "f'{'",
    "f'}'",
    "f'{}'",
    "f'{ }'",
    "f'{!r}'",
    "f'{:>5}'",
    "f'{=}'",
    "f'{x!}'",
    "f'{x!x}'",
    "f'{x!rr}'",
    "f'{x! r}'",
    "f'{x!r!s}'",
    "f'{x!r:'",
    "f'{x:'",
    "f'{x:{'",
    "f'{x:{y'",
    "f'{x:{}}'",
    "f'{x:}}'",
    "f'{x:{y}}}'",
    "f'{x:{y:{z:{w}}}}'",
    "f'{x y}'",
    "f'{x +}'",
    "f'{(x}'",
    "f'{x)}'",
    "f'{x]}'",
    "f'{[x}'",
    "f'{x[}'",
    "f'{1 2}'",
    "f'{x = = }'",
    "f'{lambda: 1}'",
    "f'{*a}'",
    "f'{**a}'",
    "f'{x for x in y}'",
    "f'{a:=1}'.x",
    "f'{x'",
    "f'x}'",
    "f'}x'",
    "f'x{'",
    "f'{{}'",
    "f'}{'",
    "f'{x}}'",
    "f'\\N{'",
    "f'\\N{NO SUCH NAME}'",
    "f'\\x4'",
    "f'\\u12'",
    "f'\\U00110000'",
    "f'{\"'",
    "f'{x['",
    "b'a' f'{x}'",
    "f'{x}' b'a'",
    "f'{b\"a\"}' b'b'",
    "f'a' rb'b'",
    "fb'a'",
    "bf'a'",
    "f'''{x'''",
    "f'{x!r:>{w}'",
    "f'{x!r:>{w!z}}'",
    "f'{await}'",
    "f'{yield}'" if False else "f'{if}'",
    "f'{x if}'",
    "f'{import}'",
    "f'{x;y}'",
    "f'{x = ;}'",
]


@pytest.mark.parametrize("literal", INVALID, ids=[repr(v)[:50] for v in INVALID])
def test_rejects_what_python_rejects(literal, plain_adapter):
    source = f"x = {literal}\n"
    if python_accepts(source):
        pytest.skip("this Python version accepts it")
    with pytest.raises(OrmError):
        parse_with(source, plain_adapter)


class TestNodes:
    def test_plain_text_only(self, plain_adapter):
        node = parse_with("x = f'abc'\n", plain_adapter).body[0].value
        assert isinstance(node, ast.JoinedStr)
        assert [type(v) for v in node.values] == [ast.Constant]
        assert node.values[0].value == "abc"

    def test_empty(self, plain_adapter):
        node = parse_with("x = f''\n", plain_adapter).body[0].value
        assert isinstance(node, ast.JoinedStr) and node.values == []

    def test_field_conversion_codes(self, plain_adapter):
        node = parse_with("x = f'{a!s}{b!r}{c!a}{d}'\n", plain_adapter).body[0].value
        assert [v.conversion for v in node.values] == [115, 114, 97, -1]

    def test_debug_text_and_default_conversion(self, plain_adapter):
        node = parse_with("x = f'{ a + 1 = }'\n", plain_adapter).body[0].value
        assert node.values[0].value == " a + 1 = "
        assert node.values[1].conversion == 114

    def test_debug_with_format_spec_keeps_no_conversion(self, plain_adapter):
        node = parse_with("x = f'{a=:>4}'\n", plain_adapter).body[0].value
        assert node.values[1].conversion == -1
        assert node.values[1].format_spec is not None

    def test_empty_format_spec_is_an_empty_joined_string(self, plain_adapter):
        node = parse_with("x = f'{a:}'\n", plain_adapter).body[0].value
        spec = node.values[0].format_spec
        assert isinstance(spec, ast.JoinedStr) and spec.values == []

    def test_nested_format_spec(self, plain_adapter):
        node = parse_with("x = f'{a:>{w}.{p}}'\n", plain_adapter).body[0].value
        spec = node.values[0].format_spec
        kinds = [type(v).__name__ for v in spec.values]
        assert kinds == ["Constant", "FormattedValue", "Constant", "FormattedValue"]

    def test_neighbouring_texts_are_merged(self, plain_adapter):
        node = parse_with("x = 'a' f'b' 'c' f'{d}' 'e'\n", plain_adapter).body[0].value
        assert [type(v).__name__ for v in node.values] == [
            "Constant",
            "FormattedValue",
            "Constant",
        ]
        assert node.values[0].value == "abc"
        assert node.values[2].value == "e"

    def test_escaped_braces_become_single_braces(self, plain_adapter):
        node = parse_with("x = f'{{a}}'\n", plain_adapter).body[0].value
        assert node.values[0].value == "{a}"

    def test_escapes_in_text_are_decoded(self, plain_adapter):
        node = parse_with("x = f'a\\tb{c}\\x41'\n", plain_adapter).body[0].value
        assert node.values[0].value == "a\tb"
        assert node.values[2].value == "A"

    def test_raw_text_is_not_decoded(self, plain_adapter):
        node = parse_with("x = rf'a\\tb{c}'\n", plain_adapter).body[0].value
        assert node.values[0].value == "a\\tb"

    def test_u_prefix_kind(self, plain_adapter):
        node = parse_with("x = u'a' f'b'\n", plain_adapter).body[0].value
        assert node.values[0].kind == "u"
        node = parse_with("x = f'a' u'b'\n", plain_adapter).body[0].value
        assert node.values[0].kind is None

    def test_every_inner_node_has_the_position_of_the_whole_string(self, plain_adapter):
        tree = parse_with("y = 1\nx = f'a{b + c}d'\n", plain_adapter)
        node = tree.body[1].value
        for sub in ast.walk(node):
            if "lineno" in sub._attributes:
                assert (sub.lineno, sub.col_offset) == (2, 4)
                assert (sub.end_lineno, sub.end_col_offset) == (2, 16)

    def test_multi_line_f_string_position(self, plain_adapter):
        tree = parse_with("x = f'''a\n{b}\nc'''\n", plain_adapter)
        node = tree.body[0].value
        assert (node.lineno, node.end_lineno) == (1, 3)

    def test_nested_f_string_is_a_joined_string_in_a_field(self, plain_adapter):
        node = parse_with("x = f\"{f'{a}'}\"\n", plain_adapter).body[0].value
        assert isinstance(node.values[0].value, ast.JoinedStr)

    def test_simple_names_use_the_fast_path_and_compile(self, plain_adapter):
        tree = parse_with("x = f'{a.b.c}{d}'\n", plain_adapter)
        namespace = {"a": type("A", (), {"b": type("B", (), {"c": 1})()})(), "d": 2}
        exec(compile(tree, "<t>", "exec"), namespace)  # noqa: S102
        assert namespace["x"] == "12"

    def test_non_ascii_name_in_a_field_is_normalised(self, plain_adapter):
        source = "x = f'{\uff58}'\n"
        assert_same(source, plain_adapter)

    def test_keyword_in_a_field_is_not_a_name(self, plain_adapter):
        with pytest.raises(OrmSyntaxError):
            parse_with("x = f'{if}'\n", plain_adapter)
        with pytest.raises(OrmSyntaxError):
            parse_with("x = f'{a.class}'\n", plain_adapter)


class TestOromo:
    def test_names_in_fields_are_translated(self, oromo_adapter):
        tree = parse_with("x = f'{of.maqaa}: {tarree(a)}'\n", oromo_adapter)
        assert ast.unparse(tree) == "x = f'{self.maqaa}: {list(a)}'"

    def test_hudhaa_keyword_in_a_field(self, oromo_adapter):
        tree = parse_with("x = f'{walitti_ida\u2019i(a)}'\n", oromo_adapter)
        assert ast.unparse(tree) == "x = f'{sum(a)}'"

    def test_format_spec_is_not_translated(self, oromo_adapter):
        tree = parse_with("x = f'{a:yoo}'\n", oromo_adapter)
        assert ast.unparse(tree) == "x = f'{a:yoo}'"

    def test_text_is_not_translated(self, oromo_adapter):
        tree = parse_with("x = f'yoo {a} hanga'\n", oromo_adapter)
        assert ast.unparse(tree) == "x = f'yoo {a} hanga'"


class TestErrors:
    def test_error_names_the_f_string_and_the_line(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("a = 1\nb = f'{x y}'\n", plain_adapter)
        assert exc.value.orm_line == 2
        assert exc.value.message.startswith("f-string:")

    @pytest.mark.parametrize(
        ("literal", "words"),
        [
            ("f'{}'", "empty"),
            ("f'}'", "single '}'"),
            ("f'{x'", "Unterminated"),
            ("f'{x!z}'", "conversion"),
            ("f'{x:{y:{z:{w}}}}'", "nested too deeply"),
            ("f'{*a}'", "starred"),
        ],
    )
    def test_error_messages(self, literal, words, plain_adapter):
        with pytest.raises(OrmError) as exc:
            parse_with(f"x = {literal}\n", plain_adapter)
        assert words in exc.value.message

    def test_bytes_cannot_be_mixed(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = b'a' f'{x}'\n", plain_adapter)
        assert "bytes" in exc.value.message

    def test_invalid_escape_in_text_warns_at_the_orm_line(self, plain_adapter):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parse_with("a = 1\nb = f'\\d{x}'\n", plain_adapter)
        assert any(w.filename == "<orm>" and w.lineno == 2 for w in caught)

    def test_bad_escape_is_an_error(self, plain_adapter):
        with pytest.raises(OrmSyntaxError):
            parse_with("x = f'\\x4{y}'\n", plain_adapter)


class TestVersionRules:
    @pytest.mark.skipif(PEP_701, reason="Python 3.12 accepts these")
    @pytest.mark.parametrize(
        "literal",
        [
            "f'{x\\n}'",
            "f'{\"a\\n\"}'",
            "f'{x # c}'",
            "f'{x:{y:{z}}}'",
            "f'{x!r }'",
            "f'{\"a\"}' f'{\"b\"}'" if False else "f'{x[\"a\"]}'",
        ],
    )
    def test_old_python_rejects_new_syntax(self, literal, plain_adapter):
        source = f"x = {literal}\n"
        if python_accepts(source):
            assert_same(source, plain_adapter)
        else:
            with pytest.raises(OrmError):
                parse_with(source, plain_adapter)

    @pytest.mark.skipif(not PEP_701, reason="needs Python 3.12")
    @pytest.mark.parametrize(
        "literal",
        [
            "f'{x\n}'",
            "f'{x # c\n}'",
            "f'{x!r }'",
            "f'{\"a\\n\"}'",
            "f'{x:{y:{z}}}'",
            "f'{f'{x}'}'",
            "f'{x:{y}{{}'",
        ],
    )
    def test_python_312_syntax(self, literal, plain_adapter):
        assert_same(f"x = {literal}\n", plain_adapter)

    def test_nesting_limit_follows_the_version(self, plain_adapter):
        deep = "x = f'{a:{b:{c}}}'\n"
        if PEP_701:
            assert_same(deep, plain_adapter)
        else:
            with pytest.raises(OrmSyntaxError):
                parse_with(deep, plain_adapter)

    def test_raw_format_spec_escapes_follow_the_version(self, plain_adapter):
        assert_same("x = rf'{a:\\n}'\n", plain_adapter)


class TestBuildJoinedStr:
    """The module on its own, with a fake expression parser."""

    @staticmethod
    def fake(text: str) -> ast.expr:
        return ast.Name(id=text.strip(), ctx=ast.Load())

    def test_text_and_field(self):
        node = build_joined_str([("f'a{b}c'", 1)], self.fake)
        assert ast.dump(node) == ast.dump(ast.parse("f'a{b}c'", mode="eval").body)

    def test_field_text_is_passed_on_unchanged(self):
        seen: list[str] = []

        def spy(text: str) -> ast.expr:
            seen.append(text)
            return self.fake(text)

        build_joined_str([("f'{ a + b !r:>{w}}'", 1)], spy)
        assert sorted(seen) == [" a + b ", "w"]

    def test_invalid_input_raises_f_string_error(self):
        with pytest.raises(FStringError):
            build_joined_str([("f'{'", 1)], self.fake)

    def test_bytes_raise(self):
        with pytest.raises(FStringError):
            build_joined_str([("b'a'", 1), ("f'{x}'", 1)], self.fake)

    def test_error_in_expression_parser_propagates(self):
        def boom(text: str) -> ast.expr:
            raise FStringError("boom")

        with pytest.raises(FStringError, match="boom"):
            build_joined_str([("f'{x}'", 1)], boom)

    def test_debug_comment_text_is_dropped_but_strings_are_kept(self):
        node = build_joined_str(
            [("f'{x # c\n=}'" if PEP_701 else "f'{x=}'", 1)], self.fake
        )
        assert node.values[0].value in ("x \n=", "x=")
        if PEP_701:
            node = build_joined_str([("f'{\"#\"=}'", 1)], self.fake)
            assert node.values[0].value == '"#"='
        else:
            with pytest.raises(FStringError):
                build_joined_str([("f'{\"#\"=}'", 1)], self.fake)


class TestVersionBranches:
    """Rules for other Python versions, run here by changing the module flags."""

    def build(self, text):
        return build_joined_str(
            [(text, 1)], lambda t: ast.Name(id=t.strip(), ctx=ast.Load())
        )

    def test_old_python_rules(self, monkeypatch):
        from oromscript import fstrings

        monkeypatch.setattr(fstrings, "_PEP_701", False)
        for text in ["f'{a\\n}'", "f'{a # c}'", "f'{\"a\"}'" if False else "f'{x!r }'"]:
            if "!r }" in text:
                continue
            with pytest.raises(FStringError):
                self.build(text)
        with pytest.raises(FStringError):
            self.build("f'{a\nb}'")
        with pytest.raises(FStringError):
            self.build("f'{'a'}'")
        with pytest.raises(FStringError):
            self.build('f"{"a"}"')
        self.build("f'''{'a'}'''")  # one quote of a triple-quoted string is fine
        with pytest.raises(FStringError):
            self.build("f'''{'''a'''}'''")

    def test_old_python_nesting_limit(self, monkeypatch):
        from oromscript import fstrings

        monkeypatch.setattr(fstrings, "_MAX_NESTING", 2)
        self.build("f'{a:{b}}'")
        with pytest.raises(FStringError, match="nested too deeply"):
            self.build("f'{a:{b:{c}}}'")

    def test_u_kind_rule_of_old_python(self):
        from oromscript.fstrings import _merge

        pieces = ["a", ast.FormattedValue(value=ast.Name(id="x"), conversion=-1), "b"]
        kinds = lambda mode: [  # noqa: E731
            v.kind for v in _merge(pieces, mode) if isinstance(v, ast.Constant)
        ]
        assert kinds("all") == ["u", "u"]
        assert kinds("before_field") == ["u", None]
        assert kinds("none") == [None, None]
        assert kinds("marked") == [None, None]

    def test_u_kind_rule_through_build(self, monkeypatch):
        from oromscript import fstrings

        monkeypatch.setattr(fstrings, "_U_KIND_ANYWHERE", False)
        node = (
            self.build("u'a'")
            if False
            else build_joined_str(
                [("u'a'", 1), ("f'{x}b'", 1)], lambda t: ast.Name(id=t, ctx=ast.Load())
            )
        )
        assert [v.kind for v in node.values if isinstance(v, ast.Constant)] == [
            "u",
            "u",
        ]
        node = build_joined_str(
            [("'a'", 1), ("f'{x}b'", 1)], lambda t: ast.Name(id=t, ctx=ast.Load())
        )
        assert [v.kind for v in node.values if isinstance(v, ast.Constant)] == [
            None,
            None,
        ]


class TestDirectErrors:
    """Errors the lexer would stop first, checked on the module alone."""

    @staticmethod
    def build(text):
        return build_joined_str(
            [(text, 1)], lambda t: ast.Name(id=t.strip(), ctx=ast.Load())
        )

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("f'\\N{abc'", "malformed"),
            ("f'{x:abc'", "expecting"),
            ("f'{x= '", "expecting"),
            ("f'{\"abc'", "unterminated"),
            ("f'{x!r'", "expecting"),
            ("f'{(x'", "expecting"),
            ("f'{x)}'", "unmatched"),
        ],
    )
    def test_error(self, text, message):
        with pytest.raises(FStringError, match=message):
            self.build(text)

    def test_debug_text_skips_comments_but_keeps_strings(self):
        if not PEP_701:
            pytest.skip("comments in fields need Python 3.12")
        node = self.build("f'{\"a#\" # c\n=}'")
        assert node.values[0].value == '"a#" \n='

    def test_debug_text_keeps_a_string_with_an_escape(self):
        from oromscript.fstrings import _Scanner

        scanner = _Scanner("", False, "'", False, 1, lambda t: ast.Name(id=t), "none")
        assert scanner.without_comments('"a\\"#" # x') == '"a\\"#" '

    def test_unterminated_string_in_debug_text(self):
        from oromscript.fstrings import _Scanner

        scanner = _Scanner("", False, "'", False, 1, lambda t: ast.Name(id=t), "none")
        assert scanner.without_comments("'abc # x") == "'abc # x"
