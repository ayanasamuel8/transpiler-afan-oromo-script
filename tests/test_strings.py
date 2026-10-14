"""Tests for string literal decoding (oromscript.strings)."""

from __future__ import annotations

import ast
import random
import sys
import threading
import warnings

import pytest

from oromscript import transpile
from oromscript.strings import decode_string_literal, split_literal

WARNING_CLASS = SyntaxWarning if sys.version_info >= (3, 12) else DeprecationWarning


def python_value(text: str) -> object:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.literal_eval(text)


@pytest.mark.parametrize(
    ("text", "prefix", "body"),
    [
        ("'abc'", "", "abc"),
        ('"abc"', "", "abc"),
        ("''", "", ""),
        ("'''abc'''", "", "abc"),
        ('"""a"b"""', "", 'a"b'),
        ("''''''", "", ""),
        ("rb'x'", "rb", "x"),
        ('Rb"""x"""', "Rb", "x"),
        ("u'x'", "u", "x"),
        ("f'{a}'", "f", "{a}"),
    ],
)
def test_split_literal(text, prefix, body):
    assert split_literal(text) == (prefix, body)


@pytest.mark.parametrize(
    "text",
    [
        "'abc'",
        "''",
        "'a\\nb'",
        "'a\\\\b'",
        "'it\\'s'",
        '"say \\"hi\\""',
        "'\\a\\b\\f\\n\\r\\t\\v'",
        "'\\x41\\101\\0'",
        "'\\u00e9\\U0001F600'",
        "'\\N{BULLET}'",
        "'\\N{LATIN SMALL LETTER E WITH ACUTE}'",
        "'''a\nb'''",
        "'a\\\nb'",
        "r'\\d\\n'",
        "rb'\\d'",
        "b'abc'",
        "b'\\x00\\xff'",
        "b'\\101'",
        "B'a'",
        "u'a'",
        "'é'",
        "'ሰላም'",
    ],
)
def test_matches_python(text):
    expected = python_value(text)
    got = decode_string_literal(text, 1)
    assert got == expected
    assert type(got) is type(expected)


@pytest.mark.parametrize(
    "text",
    [
        "'\\x'",
        "'\\x4'",
        "'\\u12'",
        "'\\U0001F60'",
        "'\\U00110000'",
        "'\\N{no such name}'",
        "'\\N{'",
        "'\\N'",
        "b'\\x'",
        "b'\\x4'",
        "b'é'",
        "b'ሰ'",
    ],
)
def test_invalid_literals_raise(text):
    with pytest.raises(ValueError):  # noqa: PT011
        decode_string_literal(text, 1)
    with pytest.raises((SyntaxError, ValueError)):
        python_value(text)


@pytest.mark.parametrize("text", ["b'\\N'", "b'\\u1234'", "b'\\U00000041'"])
def test_bytes_have_no_unicode_escapes(text):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert decode_string_literal(text, 1) == python_value(text)


def test_random_literals_match_python():
    atoms = [
 "\\n", "\\\\", "\\'", '\\"', "\\x41", "\\x4", "\\u00e9", "\\u12",
        "\\U0001F600", "\\U00110000", "\\N{BULLET}", "\\N{nope}", "\\N{", "\\101",
        "\\1234", "\\0", "\\d", "\\\n", "é", "\\q", "\\8", "\\400", "\\777", "ሰ",
        "\\N", "\\x", "\\u", "\\U", "}", "{",
    ]  # fmt: skip
    rng = random.Random(7)  # noqa: S311
    checked = 0
    for _ in range(4000):
        prefix = rng.choice(["", "r", "b", "br", "rb", "u", "R", "B", "U"])
        quote = rng.choice(["'", '"', "'''", '"""'])
        body = "".join(rng.choice(atoms) for _ in range(rng.randint(0, 6)))
        if body.endswith("\\"):
            continue
        text = f"{prefix}{quote}{body}{quote}"
        try:
            expected = python_value(text)
        except (SyntaxError, ValueError):
            with pytest.raises(ValueError):  # noqa: PT011
                decode_string_literal(text, 1)
        else:
            got = decode_string_literal(text, 1)
            assert (got, type(got)) == (expected, type(expected)), text
        checked += 1
    assert checked > 3000


class TestWarnings:
    def test_invalid_escape_names_the_orm_line(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            decode_string_literal("'\\d'", 7)
        assert len(caught) == 1
        assert caught[0].category is WARNING_CLASS
        assert (caught[0].filename, caught[0].lineno) == ("<orm>", 7)
        assert "\\d" in str(caught[0].message)

    def test_each_invalid_escape_warns_once(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            decode_string_literal("'\\d\\q\\d'", 1)
        assert len(caught) == 3

    def test_valid_and_raw_literals_do_not_warn(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            decode_string_literal("'\\n\\t\\\\\\x41'", 1)
            decode_string_literal("r'\\d\\q'", 1)
            decode_string_literal("b'\\n'", 1)
        assert caught == []

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="warning added in 3.12")
    def test_out_of_range_octal_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert decode_string_literal("'\\400'", 1) == "\u0100"
        assert len(caught) == 1

    def test_warning_filters_can_turn_it_into_an_error(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(WARNING_CLASS):
                decode_string_literal("'\\d'", 1)

    def test_transpile_reports_the_line_of_the_string(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            transpile("x = 1\ny = 2\nz = '\\d'\n")
        orm = [(w.filename, w.lineno) for w in caught if w.filename == "<orm>"]
        assert ("<orm>", 3) in orm

    def test_transpile_reports_the_line_of_an_f_string(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            transpile("x = 1\ny = f'\\d{x}'\n")
        assert any(w.filename == "<orm>" and w.lineno == 2 for w in caught)


class TestThreads:
    def test_threads_do_not_change_the_warning_filters(self):
        errors: list[BaseException] = []

        def work() -> None:
            try:
                for _ in range(200):
                    transpile("y = '\\d'\nz = f'{y}'\n")
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            before = list(warnings.filters)
            threads = [threading.Thread(target=work) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            after = list(warnings.filters)
        assert errors == []
        assert after == before

    def test_decoding_never_touches_the_filters(self):
        before = list(warnings.filters)
        decode_string_literal("'\\d'", 1)
        assert warnings.filters == before
