"""Seeded mutation tests.

Valid programs are damaged in random ways. For every result, our lexer and
parser must accept or reject the program exactly as CPython's ``ast.parse``
does, and when both accept, the trees must be equal.
"""

from __future__ import annotations

import ast
import random
import warnings

import pytest

from oromscript.adapter import Adapter
from oromscript.errors import OrmError
from oromscript.lexer import OrmLexer
from oromscript.parser import OrmParser

from .test_parser import VALID

pytestmark = pytest.mark.filterwarnings("ignore")

BASE_PROGRAMS = [
    "if a:\n    b = 1\n    if c:\n        d\n    else:\n        e\nf = (1,\n  2)\n",
    "class A:\n\tdef f(self):\n\t\treturn [1,\n\t\t\t2]\n\n\tx = 1\n",
    "x = 1 + \\\n    2\nif x:\n    pass\n",
    "def f():\n    '''doc\n    string'''\n    # comment\n    return 1\n",
    "try:\n    a\nexcept E:\n    b\nfinally:\n    c\n",
    "while 1:\n    for i in x:\n        break\n    else:\n        pass\n",
    "async def f():\n    async with a as b:\n        await c\n",
    "match x:\n    case 1:\n        pass\n    case _:\n        pass\n",
    "x = {\n  'a': 1,\n  # c\n  'b': 2,\n}\n",
    'x = f\'{a!r:>{w}} {b}\' \'c\' """d"""\n',
    "@d\ndef f(a, /, b=1, *c, d, **e) -> int:\n    return [i for i in c if i]\n",
]
WHITESPACE = [" ", "\t", "\f", "  ", "    ", "\t\t", " \t", "\t ", " \\\n", "\\\n"]
SNIPPETS = [
    "(",
    ")",
    "[",
    "]",
    "{",
    "}",
    ":",
    ",",
    ".",
    "=",
    "*",
    "**",
    '"',
    "'",
    '"""',
    "@",
    ";",
    "!",
    "|",
    "&",
    "-",
    "+",
    "<",
    ">",
    "%",
    "\\",
    "#",
    "\n",
    "    ",
    "lambda ",
    "for ",
    "in ",
    "if ",
    "else ",
    "not ",
    "async ",
    "await ",
    "yield ",
    ":=",
    "->",
    "...",
    "match ",
    "case ",
    "type ",
    "\x00",
    "\x1a",
    "\u00a0",
    "\u2028",
    "\r",
    "\r\n",
    "\v",
]


@pytest.fixture(scope="module")
def adapter() -> Adapter:
    return Adapter(lang="plain", keyword_map={}, builtin_map={}, error_messages={})


def python_accepts(source: str) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return False
    return True


def check(source: str, adapter: Adapter) -> None:
    expected = python_accepts(source)
    try:
        tree = OrmParser(adapter).parse(OrmLexer(source, adapter).tokenize())
    except OrmError:
        assert not expected, f"we reject what Python accepts: {source!r}"
        return
    assert expected, f"we accept what Python rejects: {source!r}"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert ast.dump(tree) == ast.dump(ast.parse(source)), source


def layout_mutation(rng: random.Random, source: str) -> str:
    lines = source.split("\n")
    for _ in range(rng.randint(1, 3)):
        i = rng.randrange(len(lines))
        kind = rng.random()
        if kind < 0.5:
            lead = "".join(rng.choice(WHITESPACE) for _ in range(rng.randint(0, 4)))
            lines[i] = lead + lines[i].lstrip(" \t")
        elif kind < 0.7:
            junk = [*WHITESPACE, "#c", "\\"]
            line = "".join(rng.choice(junk) for _ in range(rng.randint(0, 3)))
            lines.insert(i, line)
        elif kind < 0.85 and lines[i]:
            j = rng.randrange(len(lines[i]) + 1)
            extra = rng.choice(["\\\n", "\r\n", "\r", "\f", "\v", "\x00", "\u2028"])
            lines[i] = lines[i][:j] + extra + lines[i][j:]
        else:
            lines[i] += rng.choice(WHITESPACE)
    result = "\n".join(lines)
    return result.rstrip("\n") if rng.random() < 0.2 else result


def text_mutation(rng: random.Random, source: str) -> str:
    pos = rng.randrange(len(source) + 1)
    kind = rng.random()
    if kind < 0.35:
        return source[:pos] + source[pos + rng.randint(1, 3) :]
    if kind < 0.8:
        return source[:pos] + rng.choice(SNIPPETS) + source[pos:]
    end = min(len(source), pos + rng.randint(2, 30))
    return source[:pos] + source[end:] + source[pos:end]


def valid_sources() -> list[str]:
    import sys

    return [s for s, since in VALID if sys.version_info >= since and s.isascii()]


@pytest.mark.parametrize("seed", range(4))
def test_layout_mutations_agree_with_python(seed, adapter):
    rng = random.Random(seed)  # noqa: S311
    for _ in range(400):
        check(layout_mutation(rng, rng.choice(BASE_PROGRAMS)), adapter)


@pytest.mark.parametrize("seed", range(4))
def test_text_mutations_agree_with_python(seed, adapter):
    rng = random.Random(100 + seed)  # noqa: S311
    pool = BASE_PROGRAMS + valid_sources()
    for _ in range(400):
        check(text_mutation(rng, rng.choice(pool)), adapter)


@pytest.mark.parametrize("seed", range(2))
def test_stacked_mutations_agree_with_python(seed, adapter):
    rng = random.Random(200 + seed)  # noqa: S311
    pool = BASE_PROGRAMS + valid_sources()
    for _ in range(300):
        source = rng.choice(pool)
        for _ in range(rng.randint(2, 4)):
            mutate = rng.choice([layout_mutation, text_mutation])
            source = mutate(rng, source) if source else source
        check(source, adapter)


def test_every_valid_snippet_survives_each_single_character_deletion(adapter):
    sources = [s for s in valid_sources() if 0 < len(s) < 120][:80]
    for source in sources:
        for i in range(len(source)):
            check(source[:i] + source[i + 1 :], adapter)


# ── f-strings ────────────────────────────────────────────────────────────────

FIELD_EXPRESSIONS = [
    "x", "a.b", "f(1)", "a[1]", "x+1", "x if y else z", "(x:=1)", "'s'", '"s"',
    "x==y", "x<=y", "{1:2}[1]", "[i for i in x]", "lambda: 1", "(lambda: 1)()",
    "*a,", "1,2", "x,", "a and b", "not a", "-x", "x**2", "'a'+'b'", "x[1:2]",
    "d['k']", 'd["k"]', "f'{x}'", 'f"{x}"', "''", "(yield)", "x\n", "\nx", " x ",
    "x !r", "x ", "x#c\n", "a  ", "1 if 2 else 3", "x:y", "{}", "{1,2}",
]  # fmt: skip
SPEC_PIECES = ["", ">10", "010", "{w}", ">{w}.{p}", "%Y-%m-%d", "{w:{p}}", "x{y}z",
               "{{", "}}", "\\n", "'"]  # fmt: skip
CONVERSIONS = ["", "", "", "", "", "!r", "!s", "!a", "!x", "! r", "!"]
TEXT_PIECES = ["a", "hello ", " ", "{{", "}}", "\\n", "\\\\", "\\x41", "\\N{BULLET}",
               "\\{", "\\}", "é", "'", '"', "\\'", '\\"', "}", "{", "\n", "\\d", "\\N",
               "\\u00e9", "\\"]  # fmt: skip
PREFIXES = ["f", "F", "rf", "fr", "Rf", "fR", "f", "f", "u", "", "r", "b"]
QUOTES = ["'", '"', "'''", '"""']


def random_field(rng: random.Random) -> str:
    text = rng.choice(FIELD_EXPRESSIONS)
    debug = rng.choice(["", "", "", "="])
    conversion = rng.choice(CONVERSIONS)
    spec = ""
    if rng.random() < 0.35:
        spec = ":" + "".join(rng.choice(SPEC_PIECES) for _ in range(rng.randint(0, 3)))
    return "{" + text + debug + conversion + spec + "}"


def random_fstring_source(rng: random.Random) -> str:
    parts = []
    for _ in range(rng.choice([1, 1, 1, 2, 3])):
        body = "".join(
            random_field(rng) if rng.random() < 0.5 else rng.choice(TEXT_PIECES)
            for _ in range(rng.randint(0, 5))
        )
        quote = rng.choice(QUOTES)
        parts.append(rng.choice(PREFIXES) + quote + body + quote)
    return "x = " + " ".join(parts) + "\n"


@pytest.mark.parametrize("seed", range(6))
def test_f_strings_agree_with_python(seed, adapter):
    rng = random.Random(300 + seed)  # noqa: S311
    for _ in range(600):
        check(random_fstring_source(rng), adapter)
