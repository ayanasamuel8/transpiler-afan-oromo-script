from __future__ import annotations

import io
import sys
import tokenize

import pytest

from oromscript.adapter import Adapter
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


# ── Hand-written lexer behaviour ─────────────────────────────────────────────
T = tokenize


def lex(source: str, adapter: Adapter) -> list[tokenize.TokenInfo]:
    return OrmLexer(source, adapter).tokenize()


def kinds(source: str, adapter: Adapter) -> list[tuple[str, str]]:
    return [(T.tok_name[t.type], t.string) for t in lex(source, adapter)]


def significant(source: str, adapter: Adapter) -> list[str]:
    """Token strings without layout tokens."""
    skip = {T.NEWLINE, T.NL, T.INDENT, T.DEDENT, T.ENDMARKER, T.COMMENT}
    return [t.string for t in lex(source, adapter) if t.type not in skip]


class TestLayout:
    def test_empty_source(self, plain_adapter):
        assert kinds("", plain_adapter) == [("ENDMARKER", "")]

    def test_only_newlines(self, plain_adapter):
        assert [k for k, _ in kinds("\n\n", plain_adapter)] == ["NL", "NL", "ENDMARKER"]

    def test_only_comment_without_newline(self, plain_adapter):
        assert [k for k, _ in kinds("# hi", plain_adapter)] == [
            "COMMENT",
            "ENDMARKER",
        ]

    def test_missing_final_newline_adds_empty_newline_token(self, plain_adapter):
        tokens = lex("x = 1", plain_adapter)
        assert [T.tok_name[t.type] for t in tokens] == [
            "NAME",
            "OP",
            "NUMBER",
            "NEWLINE",
            "ENDMARKER",
        ]
        assert tokens[3].string == ""

    def test_trailing_comment_without_newline(self, plain_adapter):
        names = [k for k, _ in kinds("x  # note", plain_adapter)]
        assert names == ["NAME", "COMMENT", "NEWLINE", "ENDMARKER"]

    def test_indent_and_dedent(self, plain_adapter):
        got = [k for k, _ in kinds("if x:\n    y\nz\n", plain_adapter)]
        assert got == [
            "NAME",
            "NAME",
            "OP",
            "NEWLINE",
            "INDENT",
            "NAME",
            "NEWLINE",
            "DEDENT",
            "NAME",
            "NEWLINE",
            "ENDMARKER",
        ]

    def test_dedent_to_end_of_file_closes_every_level(self, plain_adapter):
        source = "a:\n b:\n  c:\n   d\n"
        got = [k for k, _ in kinds(source, plain_adapter)]
        assert got.count("INDENT") == 3
        assert got.count("DEDENT") == 3
        assert got[-1] == "ENDMARKER"
        assert got[-4:-1] == ["DEDENT"] * 3

    def test_multiple_dedents_on_one_line(self, plain_adapter):
        source = "a:\n b:\n  c\nd\n"
        got = [k for k, _ in kinds(source, plain_adapter)]
        assert got[-5:] == ["DEDENT", "DEDENT", "NAME", "NEWLINE", "ENDMARKER"]

    def test_blank_and_comment_lines_do_not_change_indentation(self, plain_adapter):
        source = "if x:\n    a\n\n  # odd comment\n\n    b\n"
        got = [k for k, _ in kinds(source, plain_adapter)]
        assert got.count("INDENT") == 1
        assert got.count("DEDENT") == 1

    def test_whitespace_only_line_is_blank(self, plain_adapter):
        got = [k for k, _ in kinds("if x:\n    a\n      \n    b\n", plain_adapter)]
        assert got.count("INDENT") == 1

    def test_tab_indentation(self, plain_adapter):
        got = [k for k, _ in kinds("if x:\n\ty\n", plain_adapter)]
        assert "INDENT" in got

    def test_tab_counts_as_eight_columns_for_nesting(self, plain_adapter):
        got = [k for k, _ in kinds("if x:\n\ty\n\tz\n", plain_adapter)]
        assert got.count("INDENT") == 1
        assert got.count("DEDENT") == 1

    @pytest.mark.parametrize(
        "source",
        [
            "if 1:\n\tx\n        y\n",  # tab, then eight spaces
            "if 1:\n        x\n\ty\n",  # eight spaces, then tab
            "if 1:\n    x\n\ty\n",
            "if 1:\n  if 2:\n\tx\n  y\n",
            "if 1:\n \tx\n\ty\n",
            "if 1:\n\tx\n \ty\n",
        ],
    )
    def test_mixing_tabs_and_spaces_inconsistently_is_an_error(
        self, source, plain_adapter
    ):
        with pytest.raises(OrmLexError) as exc:
            lex(source, plain_adapter)
        assert exc.value.code == "E0001"
        assert "tabs and spaces" in exc.value.message

    @pytest.mark.parametrize(
        "source",
        [
            "if 1:\n\tx\n\ty\n",
            "if 1:\n        x\n        y\n",
            "if 1:\n\tif 2:\n\t\tx\n\ty\n",
            "if 1:\n  x\n\n\t\n  y\n",  # a blank line may use any whitespace
        ],
    )
    def test_consistent_tabs_or_spaces_are_fine(self, source, plain_adapter):
        lex(source, plain_adapter)

    def test_dedent_between_a_tab_level_and_a_space_level_is_an_error(
        self, plain_adapter
    ):
        # A tab is 8 columns, so four spaces matches no outer level.
        with pytest.raises(OrmLexError) as exc:
            lex("if 1:\n\tx\n    y\n", plain_adapter)
        assert "ndent" in exc.value.message

    def test_inconsistent_dedent_is_an_error(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("if x:\n        a\n    b\n", plain_adapter)
        assert exc.value.code == "E0001"
        assert exc.value.orm_line == 3
        assert "ndent" in exc.value.message

    def test_indent_token_holds_the_whitespace(self, plain_adapter):
        tokens = lex("if x:\n    y\n", plain_adapter)
        indent = next(t for t in tokens if t.type == T.INDENT)
        assert indent.string == "    "
        assert indent.start == (2, 0)
        assert indent.end == (2, 4)

    def test_form_feed_resets_column(self, plain_adapter):
        got = [k for k, _ in kinds("\x0cx = 1\n", plain_adapter)]
        assert "INDENT" not in got

    def test_crlf_newlines(self, plain_adapter):
        crlf = kinds("if x:\r\n    y\r\nz\r\n", plain_adapter)
        lf = kinds("if x:\n    y\nz\n", plain_adapter)
        assert crlf == lf

    def test_lone_cr_newlines(self, plain_adapter):
        assert kinds("a\rb\r", plain_adapter) == kinds("a\nb\n", plain_adapter)

    def test_byte_order_mark_is_ignored(self, plain_adapter):
        assert kinds("\ufeffx = 1\n", plain_adapter) == kinds("x = 1\n", plain_adapter)

    def test_newline_inside_brackets_is_nl(self, plain_adapter):
        got = [k for k, _ in kinds("f(a,\n  b)\n", plain_adapter)]
        assert got.count("NL") == 1
        assert got.count("NEWLINE") == 1
        assert "INDENT" not in got

    def test_nested_brackets_across_lines(self, plain_adapter):
        got = [k for k, _ in kinds("x = [\n  {1: (2,\n 3)},\n]\n", plain_adapter)]
        assert got.count("NEWLINE") == 1
        assert got.count("NL") == 3

    def test_backslash_continuation(self, plain_adapter):
        got = [k for k, _ in kinds("x = 1 + \\\n    2\n", plain_adapter)]
        assert got.count("NEWLINE") == 1
        assert "INDENT" not in got

    def test_backslash_continuation_inside_brackets(self, plain_adapter):
        tokens = significant("f(1, \\\n 2)\n", plain_adapter)
        assert tokens == ["f", "(", "1", ",", "2", ")"]

    def test_backslash_at_line_start_counts_as_indentation(self, plain_adapter):
        source = "if 1:\n    a\n\\\n    b\n"
        got = [k for k, _ in kinds(source, plain_adapter)]
        assert got.count("INDENT") == 1
        assert got.count("DEDENT") == 1

    def test_backslash_then_blank_line_ends_statement(self, plain_adapter):
        got = [k for k, _ in kinds("x = 1 \\\n\n", plain_adapter)]
        assert got.count("NEWLINE") == 1

    def test_comment_after_backslash_continuation_at_end_of_file(self, plain_adapter):
        got = [k for k, _ in kinds("x = 1 \\\n# c", plain_adapter)]
        assert got == ["NAME", "OP", "NUMBER", "COMMENT", "NEWLINE", "ENDMARKER"]

    @pytest.mark.parametrize(
        "source", ["\\\n", "\\\n\\\n", "x = 1\n\\\n", "x = 1\n  \\\n"]
    )
    def test_lone_backslash_line_at_end_of_file_is_an_error(
        self, source, plain_adapter
    ):
        with pytest.raises(OrmLexError) as exc:
            lex(source, plain_adapter)
        assert "continuation" in exc.value.message

    @pytest.mark.parametrize(
        "source", ["\x00", "a\x00b", "x = 1  # c\x00", "x = '\x00'", "# \x00\n"]
    )
    def test_null_byte_anywhere_is_an_error(self, source, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex(source, plain_adapter)
        assert exc.value.code == "E0001"
        assert "x00" in exc.value.message

    def test_null_byte_position(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("a = 1\nb = 2  # \x00\n", plain_adapter)
        assert (exc.value.orm_line, exc.value.orm_col) == (2, 10)

    def test_backslash_at_end_of_file_is_an_error(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("x = 1 \\\n", plain_adapter)
        assert exc.value.code == "E0001"

    def test_backslash_followed_by_space_is_an_error(self, plain_adapter):
        with pytest.raises(OrmLexError):
            lex("x = 1 \\ \n 2\n", plain_adapter)

    def test_unclosed_bracket_at_end_of_file(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("x = 1\nf(1,\n", plain_adapter)
        assert exc.value.code == "E0001"
        assert exc.value.message == "'(' was never closed"
        assert (exc.value.orm_line, exc.value.orm_col) == (2, 2)

    @pytest.mark.parametrize("opener", ["(", "[", "{"])
    def test_each_unclosed_bracket_kind(self, opener, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex(f"x = {opener}1\n", plain_adapter)
        assert exc.value.message == f"'{opener}' was never closed"

    def test_innermost_unclosed_bracket_is_reported(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("f(a, [b,\n", plain_adapter)
        assert exc.value.message == "'[' was never closed"
        assert exc.value.orm_col == 6

    def test_closed_brackets_before_an_unclosed_one(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("f(a)(b\n", plain_adapter)
        assert exc.value.orm_col == 5

    def test_extra_closing_bracket_is_left_for_the_parser(self, plain_adapter):
        assert significant("x)\n", plain_adapter) == ["x", ")"]


class TestPositions:
    def test_single_line_positions(self, plain_adapter):
        tokens = lex("ab = 12\n", plain_adapter)
        assert (tokens[0].start, tokens[0].end) == ((1, 0), (1, 2))
        assert (tokens[1].start, tokens[1].end) == ((1, 3), (1, 4))
        assert (tokens[2].start, tokens[2].end) == ((1, 5), (1, 7))

    def test_positions_use_original_source_not_translated_text(self, oromo_adapter):
        tokens = lex("agarsiisi(1)\n", oromo_adapter)
        assert tokens[0].string == "print"
        assert tokens[0].end == (1, 9)  # 'agarsiisi' is 9 characters
        assert tokens[1].start == (1, 9)

    def test_line_numbers_advance(self, plain_adapter):
        tokens = lex("a\nb\n\nc\n", plain_adapter)
        names = [t for t in tokens if t.type == T.NAME]
        assert [t.start[0] for t in names] == [1, 2, 4]

    def test_token_line_attribute(self, plain_adapter):
        tokens = lex("a = 1\nb = 2\n", plain_adapter)
        second = next(t for t in tokens if t.string == "b")
        assert second.line == "b = 2\n"

    def test_last_line_without_newline_has_no_newline_in_line_attribute(
        self, plain_adapter
    ):
        tokens = lex("a = 1\nb = 2", plain_adapter)
        second = next(t for t in tokens if t.string == "b")
        assert second.line == "b = 2"

    def test_tokens_on_one_line_share_one_line_string(self, plain_adapter):
        tokens = [t for t in lex("a = b + c\n", plain_adapter) if t.type == T.NAME]
        assert tokens[0].line is tokens[1].line is tokens[2].line

    def test_triple_quoted_string_spans_lines(self, plain_adapter):
        tokens = lex('x = """a\nb\nc"""\ny\n', plain_adapter)
        string = next(t for t in tokens if t.type == T.STRING)
        assert string.start == (1, 4)
        assert string.end == (3, 4)
        after = next(t for t in tokens if t.string == "y")
        assert after.start == (4, 0)

    def test_endmarker_position(self, plain_adapter):
        tokens = lex("x\n", plain_adapter)
        assert tokens[-1].type == T.ENDMARKER
        assert tokens[-1].start == (2, 0)

    def test_endmarker_after_missing_final_newline(self, plain_adapter):
        tokens = lex("x", plain_adapter)
        assert tokens[-1].start == (2, 0)

    def test_error_line_and_column_both_start_at_one(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("a = 1\nb = $\n", plain_adapter)
        assert exc.value.orm_line == 2
        assert exc.value.orm_col == 5


class TestLiterals:
    @pytest.mark.parametrize(
        "text",
        [
            "0",
            "7",
            "1_000",
            "0x1F",
            "0XfF",
            "0x_ff",
            "0b101",
            "0B1_0",
            "0o17",
            "0O7",
            "1.5",
            "1.",
            ".5",
            "1e10",
            "1E-3",
            "1.5e+3",
            "1_0.0_1",
            "3j",
            "2.5J",
            "1e3j",
        ],
    )
    def test_numbers_are_one_token(self, text, plain_adapter):
        tokens = [t for t in lex(f"{text}\n", plain_adapter) if t.type == T.NUMBER]
        assert [t.string for t in tokens] == [text]

    def test_number_followed_by_name_splits(self, plain_adapter):
        assert significant("1abc\n", plain_adapter) == ["1", "abc"]

    def test_attribute_after_name_is_not_a_number(self, plain_adapter):
        assert significant("a.b\n", plain_adapter) == ["a", ".", "b"]

    def test_ellipsis_is_one_operator(self, plain_adapter):
        assert significant("...\n", plain_adapter) == ["..."]

    @pytest.mark.parametrize(
        "text",
        [
            '""',
            "''",
            '"a"',
            "'a'",
            r'"a\"b"',
            r"'a\'b'",
            '"it\'s"',
            "'say \"hi\"'",
            '"""a"""',
            "'''a'''",
            '"""a"b""c"""',
            "'''a'b''c'''",
            '"""a\nb"""',
            r'"""a\"""b"""',
            'r"\\d+"',
            'R"x"',
            'b"x"',
            'B"x"',
            'br"x"',
            'rb"x"',
            'Rb"x"',
            'u"x"',
            'U"x"',
            'f"x"',
            'F"x"',
            'fr"x"',
            'rf"x"',
            '"a\\\nb"',
        ],
    )
    def test_strings_are_one_token(self, text, plain_adapter):
        tokens = [t for t in lex(f"x = {text}\n", plain_adapter) if t.type == T.STRING]
        assert [t.string for t in tokens] == [text]

    def test_adjacent_strings_stay_separate_tokens(self, plain_adapter):
        tokens = [t for t in lex('"a" "b"\n', plain_adapter) if t.type == T.STRING]
        assert len(tokens) == 2

    def test_name_with_string_prefix_letters_is_a_name(self, plain_adapter):
        assert kinds("bu = 1\n", plain_adapter)[0] == ("NAME", "bu")

    def test_hash_inside_string_is_not_a_comment(self, plain_adapter):
        got = [k for k, _ in kinds('x = "a # b"\n', plain_adapter)]
        assert "COMMENT" not in got

    def test_unterminated_string(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex('x = "abc\n', plain_adapter)
        assert exc.value.code == "E0001"
        assert "string" in exc.value.message.lower()
        assert (exc.value.orm_line, exc.value.orm_col) == (1, 5)

    def test_unterminated_triple_quoted_string(self, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex('x = """abc\ndef\n', plain_adapter)
        assert exc.value.code == "E0001"

    @pytest.mark.parametrize(
        "source",
        [
            'x = """a"b\n',
            "x = '''a'b\n",
            'x = """ "\n',
            'x = """""\n',
            "x = '''''\n",
            'x = """\\"""\n',
            'f"""{x}" \n',
            'x = b"""a"\n',
        ],
    )
    def test_unterminated_triple_quote_is_never_an_empty_string(
        self, source, plain_adapter
    ):
        with pytest.raises(OrmLexError) as exc:
            lex(source, plain_adapter)
        assert exc.value.code == "E0001"

    def test_empty_strings_next_to_each_other(self, plain_adapter):
        got = [
            t.string
            for t in lex("x = '' '' \"\" \"\"\n", plain_adapter)
            if t.type == T.STRING
        ]
        assert got == ["''", "''", '""', '""']

    def test_empty_triple_quoted_strings(self, plain_adapter):
        got = [
            t.string
            for t in lex("x = \"\"\"\"\"\"\ny = ''''''\n", plain_adapter)
            if t.type == T.STRING
        ]
        assert got == ['""""""', "''''''"]

    def test_string_with_trailing_backslash_at_end_of_file(self, plain_adapter):
        with pytest.raises(OrmLexError):
            lex('x = "abc\\', plain_adapter)

    @pytest.mark.parametrize(
        "op",
        [
            "+",
            "-",
            "*",
            "/",
            "//",
            "%",
            "**",
            "@",
            "<<",
            ">>",
            "&",
            "|",
            "^",
            "<",
            ">",
            "<=",
            ">=",
            "==",
            "!=",
            "=",
            "+=",
            "-=",
            "*=",
            "/=",
            "//=",
            "%=",
            "**=",
            "@=",
            "<<=",
            ">>=",
            "&=",
            "|=",
            "^=",
            ":=",
            "->",
            ".",
            ",",
            ":",
            ";",
        ],
    )
    def test_operators(self, op, plain_adapter):
        ops = [t.string for t in lex(f"a {op} b\n", plain_adapter) if t.type == T.OP]
        assert ops == [op]

    def test_unary_tilde(self, plain_adapter):
        assert significant("~a\n", plain_adapter) == ["~", "a"]

    @pytest.mark.parametrize("pair", ["()", "[]", "{}"])
    def test_brackets(self, pair, plain_adapter):
        assert significant(f"{pair}\n", plain_adapter) == list(pair)

    def test_longest_operator_wins(self, plain_adapter):
        got = significant("a **= b // c\n", plain_adapter)
        assert got == ["a", "**=", "b", "//", "c"]

    @pytest.mark.parametrize("char", ["$", "?", "`", "\x00", "\xa0", "!"])
    def test_invalid_characters(self, char, plain_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex(f"x {char} y\n", plain_adapter)
        assert exc.value.code == "E0001"
        assert (exc.value.orm_line, exc.value.orm_col) == (1, 3)

    def test_unicode_identifier(self, plain_adapter):
        assert significant("naïve = 1\n", plain_adapter) == ["naïve", "=", "1"]

    def test_identifier_that_python_would_reject(self, plain_adapter):
        with pytest.raises(OrmLexError):
            lex("x\u00b2 = 1\n", plain_adapter)  # superscript two

    def test_identifiers_are_normalised_like_python(self, plain_adapter):
        # The fullwidth letter and the "fi" ligature become plain letters.
        assert significant("\uff58 = \ufb01\n", plain_adapter) == ["x", "=", "fi"]

    def test_normalised_identifier_keeps_original_width_in_positions(
        self, plain_adapter
    ):
        tokens = lex("\ufb01 = 1\n", plain_adapter)
        assert tokens[0].string == "fi"
        assert tokens[0].end == (1, 1)
        assert tokens[1].start == (1, 2)

    def test_underscore_names(self, plain_adapter):
        assert significant("_ __x__ _1\n", plain_adapter) == ["_", "__x__", "_1"]


class TestTranslation:
    def test_keyword_translation(self, oromo_adapter):
        assert significant("yoo Dhugaa:\n", oromo_adapter) == ["if", "True", ":"]

    def test_all_keywords_are_translated(self, oromo_adapter):
        for py_word, local in oromo_adapter.keyword_map.items():
            got = significant(f"{local}\n", oromo_adapter)
            assert got == [py_word], local

    def test_all_builtins_are_translated(self, oromo_adapter):
        for py_word, local in oromo_adapter.builtin_map.items():
            got = significant(f"{local}\n", oromo_adapter)
            assert got == [py_word], local

    def test_python_names_are_not_translated_back(self, oromo_adapter):
        assert significant("print(len)\n", oromo_adapter) == ["print", "(", "len", ")"]

    def test_multi_word_keyword_becomes_one_name_token(self, oromo_adapter):
        tokens = lex("kennii_irra x\n", oromo_adapter)
        assert tokens[0].string == "yield from"
        assert tokens[0].type == T.NAME

    def test_hudhaa_builtin_with_ascii_apostrophe(self, oromo_adapter):
        assert significant("walitti_ida'i([1])\n", oromo_adapter)[0] == "sum"

    @pytest.mark.parametrize("mark", ["\u2019", "\u02bc", "\u2018"])
    def test_hudhaa_builtin_with_curly_apostrophe(self, mark, oromo_adapter):
        assert significant(f"walitti_ida{mark}i([1])\n", oromo_adapter)[0] == "sum"

    def test_hudhaa_builtin_position_uses_original_text(self, oromo_adapter):
        tokens = lex("walitti_ida'i(1)\n", oromo_adapter)
        assert tokens[0].end == (1, 13)
        assert tokens[1].start == (1, 13)

    def test_hudhaa_keyword_followed_by_more_letters_is_not_the_keyword(
        self, oromo_adapter
    ):
        # The apostrophe then starts a string, which is never closed.
        with pytest.raises(OrmLexError):
            lex("walitti_ida'ix = 1\n", oromo_adapter)

    def test_hudhaa_keyword_inside_larger_name_is_not_translated(self, oromo_adapter):
        with pytest.raises(OrmLexError):
            lex("xwalitti_ida'i\n", oromo_adapter)
        assert significant("xwalitti_ida\n", oromo_adapter) == ["xwalitti_ida"]

    def test_python_string_after_name_still_works(self, oromo_adapter):
        assert significant("agarsiisi'hi'\n", oromo_adapter) == ["print", "'hi'"]

    def test_names_inside_strings_are_kept(self, oromo_adapter):
        got = significant("'yoo' \"hanga\"\n", oromo_adapter)
        assert got == ["'yoo'", '"hanga"']

    def test_names_inside_comments_are_kept(self, oromo_adapter):
        tokens = lex("x  # yoo hanga\n", oromo_adapter)
        comment = next(t for t in tokens if t.type == T.COMMENT)
        assert comment.string == "# yoo hanga"

    def test_untranslated_name_object_is_same_text(self, oromo_adapter):
        assert significant("maqaa\n", oromo_adapter) == ["maqaa"]

    def test_lexer_does_not_mutate_input(self, oromo_adapter):
        source = "yoo dhugaa:\n    deebi 1\n"
        copy = str(source)
        OrmLexer(source, oromo_adapter).tokenize()
        assert source == copy

    def test_tokenize_is_repeatable(self, oromo_adapter):
        lexer = OrmLexer("yoo dhugaa:\n    deebi 1\n", oromo_adapter)
        assert [t.string for t in lexer.tokenize()] == [
            t.string for t in lexer.tokenize()
        ]

    def test_custom_adapter_with_other_language(self):
        adapter = Adapter(
            lang="test",
            keyword_map={"if": "wenn", "print": "drucke"},
            builtin_map={},
            error_messages={},
        )
        assert significant("wenn x: drucke(x)\n", adapter) == [
            "if",
            "x",
            ":",
            "print",
            "(",
            "x",
            ")",
        ]


class TestFStrings:
    def test_names_in_fields_are_translated(self, oromo_adapter):
        tokens = lex("f'{agarsiisi}'\n", oromo_adapter)
        assert next(t for t in tokens if t.type == T.STRING).string == "f'{print}'"

    def test_literal_text_is_not_translated(self, oromo_adapter):
        tokens = lex("f'yoo {yoo} hanga'\n", oromo_adapter)
        assert (
            next(t for t in tokens if t.type == T.STRING).string == "f'yoo {if} hanga'"
        )

    def test_attribute_in_field(self, oromo_adapter):
        s = next(t for t in lex("f'{of.maqaa}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{self.maqaa}'"

    def test_escaped_braces_are_literal(self, oromo_adapter):
        s = next(
            t for t in lex("f'{{yoo}} {yoo}'\n", oromo_adapter) if t.type == T.STRING
        )
        assert s.string == "f'{{yoo}} {if}'"

    def test_format_spec_text_is_not_translated(self, oromo_adapter):
        s = next(t for t in lex("f'{yoo:yoo}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{if:yoo}'"

    def test_nested_field_in_format_spec(self, oromo_adapter):
        s = next(t for t in lex("f'{x:{yoo}}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{x:{if}}'"

    def test_conversion_letter_is_not_translated(self, oromo_adapter):
        s = next(t for t in lex("f'{yoo!r}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{if!r}'"

    def test_not_equal_inside_field(self, oromo_adapter):
        s = next(
            t for t in lex("f'{yoo != hanga}'\n", oromo_adapter) if t.type == T.STRING
        )
        assert s.string == "f'{if != for}'"

    def test_self_documenting_field(self, oromo_adapter):
        s = next(t for t in lex("f'{yoo=}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{if=}'"

    def test_dict_and_slice_colons_do_not_start_a_format_spec(self, oromo_adapter):
        s = next(
            t
            for t in lex("f'{ {yoo: 1}[yoo] } {a[1:2]}'\n", oromo_adapter)
            if t.type == T.STRING
        )
        assert s.string == "f'{ {if: 1}[if] } {a[1:2]}'"

    def test_lambda_in_parentheses(self, oromo_adapter):
        s = next(
            t
            for t in lex("f'{(lambda yoo: yoo)(1)}'\n", oromo_adapter)
            if t.type == T.STRING
        )
        assert s.string == "f'{(lambda if: if)(1)}'"

    def test_string_inside_field_is_not_translated(self, oromo_adapter):
        s = next(t for t in lex("f\"{'yoo'}\"\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f\"{'yoo'}\""

    def test_brace_inside_string_inside_field(self, oromo_adapter):
        s = next(
            t for t in lex("f\"{'}'} {yoo}\"\n", oromo_adapter) if t.type == T.STRING
        )
        assert s.string == "f\"{'}'} {if}\""

    def test_nested_f_string_in_field(self, oromo_adapter):
        s = next(
            t for t in lex("f\"{f'{yoo}'}\"\n", oromo_adapter) if t.type == T.STRING
        )
        assert s.string == "f\"{f'{if}'}\""

    def test_same_quote_nested_string_python_312_style(self, oromo_adapter):
        s = next(t for t in lex("f'{f'{yoo}'}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'{f'{if}'}'"
        # the whole literal is one token
        assert (
            len(
                [t for t in lex("f'{f'{yoo}'}'\n", oromo_adapter) if t.type == T.STRING]
            )
            == 1
        )

    def test_triple_quoted_f_string_across_lines(self, oromo_adapter):
        tokens = lex('x = f"""a\n{yoo}\nb"""\ny\n', oromo_adapter)
        s = next(t for t in tokens if t.type == T.STRING)
        assert s.string == 'f"""a\n{if}\nb"""'
        assert s.start == (1, 4)
        assert s.end == (3, 4)
        assert next(t for t in tokens if t.string == "y").start == (4, 0)

    def test_newline_inside_field_of_triple_quoted(self, oromo_adapter):
        tokens = lex('f"""{\nyoo\n}"""\n', oromo_adapter)
        s = next(t for t in tokens if t.type == T.STRING)
        assert s.string == 'f"""{\nif\n}"""'

    def test_raw_f_string(self, oromo_adapter):
        s = next(t for t in lex("rf'\\d{yoo}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "rf'\\d{if}'"

    def test_escape_in_f_string_does_not_end_it(self, oromo_adapter):
        tokens = lex("f'a\\'{yoo}'\n", oromo_adapter)
        assert next(t for t in tokens if t.type == T.STRING).string == "f'a\\'{if}'"

    def test_backslash_before_field_in_non_raw(self, oromo_adapter):
        s = next(t for t in lex("f'\\{yoo}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'\\{if}'"

    def test_named_unicode_escape_is_not_a_field(self, oromo_adapter):
        s = next(
            t
            for t in lex("f'\\N{BULLET} {yoo}'\n", oromo_adapter)
            if t.type == T.STRING
        )
        assert s.string == "f'\\N{BULLET} {if}'"

    def test_hudhaa_keyword_in_field(self, oromo_adapter):
        s = next(
            t
            for t in lex("f'{walitti_ida\u2019i([1])}'\n", oromo_adapter)
            if t.type == T.STRING
        )
        assert s.string == "f'{sum([1])}'"

    def test_prefixed_string_inside_field(self, oromo_adapter):
        s = next(
            t for t in lex("f'{b\"yoo\"} {yoo}'\n", oromo_adapter) if t.type == T.STRING
        )
        assert s.string == "f'{b\"yoo\"} {if}'"

    def test_unterminated_field(self, oromo_adapter):
        with pytest.raises(OrmLexError) as exc:
            lex("f'{yoo'\n", oromo_adapter)
        assert exc.value.code == "E0001"

    def test_unterminated_f_string_with_nested_quote(self, oromo_adapter):
        with pytest.raises(OrmLexError):
            lex("f'abc {'x' \n", oromo_adapter)

    def test_empty_f_string(self, oromo_adapter):
        s = next(t for t in lex("f''\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f''"

    def test_f_string_with_no_fields(self, oromo_adapter):
        s = next(t for t in lex("f'yoo'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "f'yoo'"

    def test_plain_string_that_looks_like_a_field_is_untouched(self, oromo_adapter):
        s = next(t for t in lex("'{yoo}'\n", oromo_adapter) if t.type == T.STRING)
        assert s.string == "'{yoo}'"

    def test_non_f_string_with_f_in_name(self, oromo_adapter):
        got = significant("sf'x'\n", oromo_adapter)
        assert got == ["sf", "'x'"]


class TestAgainstStandardTokenizer:
    """The lexer must agree with ``tokenize`` on plain Python."""

    SOURCES = [
        "x = 1\n",
        "def f(a, b=2, *c, **d):\n    return a + b\n",
        "class A(B):\n    x: int = 3\n\n    def m(self):\n        pass\n",
        "if a:\n    b\nelif c:\n    d\nelse:\n    e\n",
        "for i in range(10):\n    if i % 2:\n        continue\n    print(i)\n",
        "try:\n    x\nexcept E as e:\n    y\nfinally:\n    z\n",
        "x = [\n    1,\n    2,  # two\n]\n",
        "s = '''a\nb'''\nt = 1\n",
        "a = b \\\n    + c\n",
        "lambda x: (yield)\n",
        "x = {1: 2, **y}\n",
        "x = a if b else c\n",
        "async def f():\n    await g()\n    async with a as b:\n        pass\n",
        "@d\ndef f(): ...\n",
        "x = 0x1F + 0b1 + 0o7 + 1_0 + 1.5e3 + 2j\n",
        "x = a @ b // c ** d >> e << f & g | h ^ ~i\n",
        "def f() -> int: return 1\n",
        "if (n := 10) > 5: pass\n",
        "a = 1; b = 2\n",
        "# only a comment\n",
        "x = 1  # trailing\n",
        "\n\n  # indented comment\nx = 1\n",
        "x = 1",
    ]

    @pytest.mark.parametrize("source", SOURCES)
    def test_same_tokens(self, source, plain_adapter):
        expected = [
            (t.type, t.string, t.start, t.end)
            for t in tokenize.generate_tokens(io.StringIO(source).readline)
        ]
        got = [(t.type, t.string, t.start, t.end) for t in lex(source, plain_adapter)]
        assert got == expected

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="needs 3.12 tokenizer")
    def test_same_tokens_on_own_source_files(self, plain_adapter):
        from pathlib import Path

        import oromscript

        for path in Path(oromscript.__file__).parent.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            expected = _stdlib_tokens_with_whole_fstrings(source)
            got = [
                (t.type, t.string, t.start, t.end) for t in lex(source, plain_adapter)
            ]
            assert got == expected, path.name


def _stdlib_tokens_with_whole_fstrings(source: str) -> list[tuple[object, ...]]:
    """Tokens from ``tokenize``, with each f-string folded into one STRING."""
    lines = source.split("\n")

    def offset(pos: tuple[int, int]) -> int:
        return sum(len(line) + 1 for line in lines[: pos[0] - 1]) + pos[1]

    out: list[tuple[object, ...]] = []
    depth = 0
    start = (0, 0)
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == getattr(T, "FSTRING_START", -1):
            if depth == 0:
                start = tok.start
            depth += 1
        elif tok.type == getattr(T, "FSTRING_END", -1):
            depth -= 1
            if depth == 0:
                text = source[offset(start) : offset(tok.end)]
                out.append((T.STRING, text, start, tok.end))
        elif depth == 0:
            out.append((tok.type, tok.string, tok.start, tok.end))
    return out


class TestFStringInternals:
    def test_unclosed_named_unicode_escape(self, oromo_adapter):
        with pytest.raises(OrmLexError):
            lex("f'\\N{abc'\n", oromo_adapter)

    def test_apostrophe_after_a_name_in_a_field_is_not_a_keyword(self, oromo_adapter):
        tokens = lex("f\"{a'b'}\"\n", oromo_adapter)
        string = next(t for t in tokens if t.type == T.STRING)
        assert string.string == "f\"{a'b'}\""

    def test_scan_stops_at_a_raw_newline_in_a_short_literal(self, oromo_adapter):
        lexer = OrmLexer("", oromo_adapter)
        with pytest.raises(OrmLexError):
            lexer._scan_fstring("f'ab\ncd'", 0)

    def test_scan_reports_a_missing_closing_quote(self, oromo_adapter):
        lexer = OrmLexer("", oromo_adapter)
        with pytest.raises(OrmLexError) as exc:
            lexer._scan_fstring("f'abc", 0)
        assert "string" in exc.value.message.lower()

    def test_scan_reports_the_line_of_a_missing_quote(self, oromo_adapter):
        lexer = OrmLexer("", oromo_adapter)
        with pytest.raises(OrmLexError) as exc:
            lexer._scan_fstring("x = 1\ny = f'''abc", 10)
        assert exc.value.orm_line == 2


class TestReviewFixes:
    @pytest.mark.parametrize(
        "source",
        [
            "x = f'{a\n}'\n",
            "x = f'{a:\n}'\n",
            "x = f'{a # c\n}'\n",
            'x = f"{a\n}"\n',
            "x = rf'{a\n}'\n",
            "x = fr'{a\n}'\n",
            'x = F"{a\n}"\n',
        ],
    )
    def test_newline_inside_an_f_string_field(self, source, plain_adapter):
        tokens = lex(source, plain_adapter)
        strings = [t for t in tokens if t.type == T.STRING]
        assert len(strings) == 1
        assert strings[0].start == (1, 4)
        assert strings[0].end[0] == 2

    def test_newline_inside_a_field_keeps_line_numbers(self, plain_adapter):
        tokens = lex("x = f'{a\n}'\ny = 1\n", plain_adapter)
        assert next(t for t in tokens if t.string == "y").start == (3, 0)

    def test_newline_in_the_literal_part_of_a_short_f_string_is_an_error(
        self, plain_adapter
    ):
        with pytest.raises(OrmLexError):
            lex("x = f'a\nb'\n", plain_adapter)

    def test_name_ending_in_f_next_to_a_quote_is_not_an_f_string(self, plain_adapter):
        # "bf" is not an f-string prefix, so this is a name and a string.
        assert significant("bf'x'\n", plain_adapter) == ["bf", "'x'"]

    @pytest.mark.parametrize(
        "name",
        ["नमस्ते", "a\u0301", "e\u0301\u0302", "ሰላም", "ñandú", "日本語"],
    )
    def test_names_with_combining_marks_and_other_scripts(self, name, plain_adapter):
        got = significant(f"{name} = 1\n", plain_adapter)
        assert len(got) == 3
        assert got[1:] == ["=", "1"]

    @pytest.mark.parametrize(
        ("source", "column"),
        [
            ("x\u00b2 = 1\n", 2),
            ("ab\u2014cd = 1\n", 3),
            ("x = a\u201cb\n", 6),
            ("\u00b2 = 1\n", 1),
        ],
    )
    def test_invalid_character_in_a_name_is_reported_at_that_character(
        self, source, column, plain_adapter
    ):
        with pytest.raises(OrmLexError) as exc:
            lex(source, plain_adapter)
        assert exc.value.orm_col == column

    def test_error_columns_start_at_one(self, plain_adapter):
        for source, column in [
            ("$\n", 1),
            ("x = 'a\n", 5),
            ("x = (1\n", 5),
            ("if 1:\n\tx\n        y\n", 9),
        ]:
            with pytest.raises(OrmLexError) as exc:
                lex(source, plain_adapter)
            assert exc.value.orm_col == column, source


class TestRemainingBranches:
    def test_first_invalid_character_helper(self):
        from oromscript.lexer import _first_invalid_character

        assert _first_invalid_character("ab²c") == 2
        assert _first_invalid_character("²") == 0
        assert _first_invalid_character("abc") == 0

    def test_straight_apostrophe_keyword_in_a_field(self, oromo_adapter):
        tokens = lex('f"{walitti_ida\'i([1])}"\n', oromo_adapter)
        string = next(t for t in tokens if t.type == T.STRING)
        assert string.string == 'f"{sum([1])}"'

    def test_backslash_inside_a_string_inside_a_field(self, oromo_adapter):
        tokens = lex("f\"{'a\\'b'} {yoo}\"\n", oromo_adapter)
        string = next(t for t in tokens if t.type == T.STRING)
        assert string.string == "f\"{'a\\'b'} {if}\""

    def test_curly_apostrophe_keyword_in_a_field(self, oromo_adapter):
        tokens = lex("f'{walitti_ida’i([1])}'\n", oromo_adapter)
        string = next(t for t in tokens if t.type == T.STRING)
        assert string.string == "f'{sum([1])}'"
