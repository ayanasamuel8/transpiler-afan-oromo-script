import ast
import glob
import sys
import sysconfig
import tokenize
import warnings

import pytest

import oromscript.parser as parser_module
from oromscript.adapter import Adapter
from oromscript.errors import OrmError, OrmLexError, OrmSyntaxError
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
    source = "yoo :"  # missing condition
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    with pytest.raises(OrmSyntaxError) as exc_info:
        OrmParser(oromo_adapter).parse(tokens)
    assert exc_info.value.code == "E0010"
    assert exc_info.value.orm_line >= 1


# ── Hand-written parser behaviour ────────────────────────────────────────────


def parse_with(source: str, adapter: Adapter) -> ast.AST:
    return OrmParser(adapter).parse(OrmLexer(source, adapter).tokenize())


def positions(tree: ast.AST) -> list[tuple[object, ...]]:
    """Node positions, skipping the inside of f-strings."""
    out: list[tuple[object, ...]] = []

    def walk(node: ast.AST) -> None:
        out.append(
            (
                type(node).__name__,
                getattr(node, "lineno", None),
                getattr(node, "col_offset", None),
                getattr(node, "end_lineno", None),
                getattr(node, "end_col_offset", None),
            )
        )
        if isinstance(node, ast.JoinedStr):
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(tree)
    return out


def assert_same_as_python(source: str, adapter: Adapter) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        expected = ast.parse(source)
    got = parse_with(source, adapter)
    assert ast.dump(got) == ast.dump(expected)
    assert positions(got) == positions(expected)


V310 = (3, 10)
V311 = (3, 11)
V312 = (3, 12)
V313 = (3, 13)
V314 = (3, 14)

# (source, minimum Python version)
VALID: list[tuple[str, tuple[int, int]]] = [
    # simple statements
    ("pass\n", V310),
    ("x = 1\n", V310),
    ("x = 1", V310),
    ("a = b = c = 1\n", V310),
    ("a, b = 1, 2\n", V310),
    ("a, = x\n", V310),
    ("[a, b] = x\n", V310),
    ("(a, b) = x\n", V310),
    ("a, *b = x\n", V310),
    ("*a, b = x\n", V310),
    ("a.b = 1\n", V310),
    ("a[0] = 1\n", V310),
    ("a[0].b[1] = 1\n", V310),
    ("x = 1,\n", V310),
    ("x = *a, b\n", V310),
    ("x: int\n", V310),
    ("x: int = 1\n", V310),
    ("(x): int = 1\n", V310),
    ("a.b: int\n", V310),
    ("a[0]: int = 2\n", V310),
    ("x += 1\n", V310),
    ("x -= 1\nx *= 2\nx /= 3\nx //= 4\nx %= 5\nx **= 6\n", V310),
    ("x @= y\nx <<= 1\nx >>= 1\nx &= 1\nx |= 1\nx ^= 1\n", V310),
    ("a.b += 1\n", V310),
    ("a[0] += 1\n", V310),
    ("x = yield\n", V310),
    ("def f():\n    x = yield 1\n    y = yield from z\n", V310),
    ("def f():\n    x += yield\n", V310),
    ("def f():\n    x: int = yield\n", V310),
    ("def f():\n    yield\n    yield 1, 2\n    yield from g()\n", V310),
    ("def f():\n    return\n", V310),
    ("def f():\n    return 1, 2\n", V310),
    ("def f():\n    return *a, b\n", V310),
    ("raise\n", V310),
    ("raise E\n", V310),
    ("raise E from e\n", V310),
    ("global a\n", V310),
    ("def f():\n    global a, b\n    nonlocal c\n", V310),
    ("del a\n", V310),
    ("del a, b\n", V310),
    ("del (a, b)\n", V310),
    ("del (a), b\n", V310),
    ("del a[0], b.c\n", V310),
    ("del a,\n", V310),
    ("assert x\n", V310),
    ("assert x, 'msg'\n", V310),
    ("a; b; c\n", V310),
    ("a;\n", V310),
    ("a; b;\n", V310),
    ("break\n", V310),
    ("continue\n", V310),
    ("import a\n", V310),
    ("import a.b.c\n", V310),
    ("import a as b, c.d as e\n", V310),
    ("from a import b\n", V310),
    ("from a.b import c as d, e\n", V310),
    ("from . import a\n", V310),
    ("from .. import a\n", V310),
    ("from ... import a\n", V310),
    ("from .... import a\n", V310),
    ("from .a import b\n", V310),
    ("from ...a.b import c\n", V310),
    ("from a import *\n", V310),
    ("from a import (b, c)\n", V310),
    ("from a import (b, c,)\n", V310),
    ("from a import (\n    b,\n    c as d,\n)\n", V310),
    ("from __future__ import annotations\n", V310),
    # expressions: literals
    ("x = 0\n", V310),
    ("x = 0x1F\n", V310),
    ("x = 0b101\n", V310),
    ("x = 0o17\n", V310),
    ("x = 1_000_000\n", V310),
    ("x = 1.5\nx = 1.\nx = .5\nx = 1e3\nx = 1E-3\nx = 1.5e+3\n", V310),
    ("x = 3j\nx = 1.5J\nx = 1e3j\n", V310),
    ("x = 00\n", V310),
    ("x = 09.5\n", V310),
    ("x = 0e0\n", V310),
    ("x = 10**100\n", V310),
    ("x = 123456789012345678901234567890\n", V310),
    ("x = True\nx = False\nx = None\n", V310),
    ("x = ...\n", V310),
    ("x = 'a'\n", V310),
    ('x = "a" "b"\n', V310),
    ("x = ('a'\n     'b')\n", V310),
    ("x = u'a'\n", V310),
    ("x = r'\\d'\n", V310),
    ("x = b'a'\n", V310),
    ("x = b'a' b'b'\n", V310),
    ("x = rb'a\\x'\n", V310),
    ("x = ''\nx = \"\"\nx = ''''''\nx = \"\"\"\"\"\"\n", V310),
    ("x = '''a\nb'''\n", V310),
    ("x = 'a\\nb'\n", V310),
    ("x = '\\u00e9\\x41\\101'\n", V310),
    ("x = 'tab\\there'\n", V310),
    ("x = '\\N{BULLET}'\n", V310),
    ("x = 'a' 'b' \"c\"\n", V310),
    ("x = u'a' 'b'\n", V310),
    ("x = 'a' u'b'\n", V310),
    ("x = 'it\\'s'\n", V310),
    ('x = "say \\"hi\\""\n', V310),
    ("x = f'a'\n", V310),
    ("x = f'{a}'\n", V310),
    ("x = f'{a} and {b!r:>10}'\n", V310),
    ("x = f'{a:{w}.{p}}'\n", V310),
    ("x = f'{{literal}}'\n", V310),
    ("x = f'{a}' 'b' f'{c}'\n", V310),
    ("x = f'a' 'b'\n", V310),
    ("x = rf'\\d{a}'\n", V310),
    ("x = f'{a=}'\n", V310),
    ("x = f'''{a}\n{b}'''\n", V310),
    ("x = f'{a[\"k\"]}'\n", V310),
    ("x = f'{f\"{a}\"}'\n", V310),
    ("x = f'{f'{a}'}'\n", V312),
    # expressions: operators
    ("x = a + b - c\n", V310),
    ("x = a * b / c // d % e @ f\n", V310),
    ("x = a ** b ** c\n", V310),
    ("x = -a ** -b\n", V310),
    ("x = (-a) ** b\n", V310),
    ("x = ~a + +b - -c\n", V310),
    ("x = - - a\n", V310),
    ("x = a << b >> c\n", V310),
    ("x = a & b | c ^ d\n", V310),
    ("x = a | b & c ^ d\n", V310),
    ("x = a + b * c\n", V310),
    ("x = (a + b) * c\n", V310),
    ("x = a - b - c\n", V310),
    ("x = a < b < c\n", V310),
    ("x = a == b != c >= d <= e > f\n", V310),
    ("x = a in b\nx = a not in b\nx = a is b\nx = a is not b\n", V310),
    ("x = not a\nx = not not a\n", V310),
    ("x = not a == b\n", V310),
    ("x = a and b or c and d\n", V310),
    ("x = a or b or c\n", V310),
    ("x = a and b and c\n", V310),
    ("x = a if b else c\n", V310),
    ("x = a if b else c if d else e\n", V310),
    ("x = (a if b else c) if d else e\n", V310),
    ("x = a or b if c else d\n", V310),
    ("x = lambda: 1\n", V310),
    ("x = lambda a, b=2, *c, d, e=5, **f: a\n", V310),
    ("x = lambda a, /, b: a\n", V310),
    ("x = lambda *, a: a\n", V310),
    ("x = lambda: (yield)\n", V310),
    ("x = lambda a: lambda b: a + b\n", V310),
    ("x = a if b else lambda: c\n", V310),
    ("x = (y := 10)\n", V310),
    ("if (n := len(a)) > 3: pass\n", V310),
    ("x = [y := 1, y ** 2]\n", V310),
    ("f(y := 1)\n", V310),
    ("a[y := 1]\n", V310),
    ("x = {y := 1}\n", V310),
    ("x = [z for x in a if (z := f(x))]\n", V310),
    ("x = await_\n", V310),
    (
        "async def f():\n    x = await g()\n    await h\n    y = await a ** 2\n    z = -await a\n",
        V310,
    ),
    # atoms and trailers
    ("x = ()\n", V310),
    ("x = (1,)\n", V310),
    ("x = (1, 2)\n", V310),
    ("x = (1, 2,)\n", V310),
    ("x = ((1))\n", V310),
    ("x = (\n    1,\n    2,\n)\n", V310),
    ("x = []\n", V310),
    ("x = [1]\n", V310),
    ("x = [1, 2,]\n", V310),
    ("x = [*a, *b]\n", V310),
    ("x = {}\n", V310),
    ("x = {1}\n", V310),
    ("x = {1, 2,}\n", V310),
    ("x = {*a, 1}\n", V310),
    ("x = {1: 2}\n", V310),
    ("x = {1: 2, 3: 4,}\n", V310),
    ("x = {**a}\n", V310),
    ("x = {**a, 'b': 1, **c}\n", V310),
    ("x = {1: 2, **a}\n", V310),
    ("x = a.b.c\n", V310),
    ("x = a().b().c\n", V310),
    ("x = a[0][1][2]\n", V310),
    ("x = a(1)(2)(3)\n", V310),
    ("x = a.b[0](1).c\n", V310),
    ("x = 'abc'.upper()\n", V310),
    ("x = (1).real\n", V310),
    ("x = [1, 2][0]\n", V310),
    ("x = {1: 2}[1]\n", V310),
    ("x = a[1:2]\n", V310),
    ("x = a[:]\n", V310),
    ("x = a[::]\n", V310),
    ("x = a[1:]\n", V310),
    ("x = a[:2]\n", V310),
    ("x = a[::3]\n", V310),
    ("x = a[1:2:3]\n", V310),
    ("x = a[1:2:]\n", V310),
    ("x = a[:, 1]\n", V310),
    ("x = a[1:2, ::3]\n", V310),
    ("x = a[1, 2]\n", V310),
    ("x = a[1,]\n", V310),
    ("x = a[...]\n", V310),
    ("x = a[..., 1]\n", V310),
    ("x = a[b:c, d]\n", V310),
    ("x = a[lambda: 1]\n", V310),
    ("x = a[1 if b else 2:3]\n", V310),
    ("x = a[*b]\n", V311),
    ("x = a[1, *b]\n", V311),
    # calls
    ("f()\n", V310),
    ("f(1)\n", V310),
    ("f(1, 2,)\n", V310),
    ("f(a=1)\n", V310),
    ("f(1, a=2, b=3)\n", V310),
    ("f(*a)\n", V310),
    ("f(**a)\n", V310),
    ("f(*a, *b, c, d=1, *e, **f, **g)\n", V310),
    ("f(a=1, *b)\n", V310),
    ("f(a=1, **b, c=2)\n", V310),
    ("f(x for x in y)\n", V310),
    ("f((x for x in y), 1)\n", V310),
    ("f(\n    1,\n    2,\n)\n", V310),
    ("f(a if b else c)\n", V310),
    ("f(lambda: 1, lambda x: x)\n", V310),
    ("f(a)(b)[c].d(e)\n", V310),
    ("print(*args, sep='')\n", V310),
    ("f(a, b)(c)(d)\n", V310),
    ("f(**{'a': 1})\n", V310),
    # comprehensions
    ("x = [a for a in b]\n", V310),
    ("x = [a for a in b if c]\n", V310),
    ("x = [a for a in b if c if d]\n", V310),
    ("x = [a for a in b for c in d]\n", V310),
    ("x = [a for a in b if c for d in e if f]\n", V310),
    ("x = [(a, b) for a, b in c]\n", V310),
    ("x = [a for (a, b) in c]\n", V310),
    ("x = [a for [a, b] in c]\n", V310),
    ("x = [a for a, in c]\n", V310),
    ("x = [a for *a, b in c]\n", V310),
    ("x = [a for a.b in c]\n", V310),
    ("x = [a for a[0] in c]\n", V310),
    ("x = [a if b else c for d in e]\n", V310),
    ("x = [a for a in b if c or d]\n", V310),
    ("x = [a for a in (b if c else d)]\n", V310),
    ("x = [a for a in b or c]\n", V310),
    ("x = {a for a in b}\n", V310),
    ("x = {a: b for a, b in c}\n", V310),
    ("x = {a: b for a in c if d}\n", V310),
    ("x = (a for a in b)\n", V310),
    ("x = (a for a in b if c)\n", V310),
    ("x = sum(a for a in b)\n", V310),
    ("async def f():\n    x = [a async for a in b]\n", V310),
    ("async def f():\n    x = [await a for a in b]\n", V310),
    ("async def f():\n    x = {a: b async for a, b in c}\n", V310),
    ("async def f():\n    x = (a async for a in b async for c in d)\n", V310),
    ("x = [a for a in b if c in d]\n", V310),
    ("x = [a for a in b if not c]\n", V310),
    ("x = [[a for a in b] for b in c]\n", V310),
    # if / while / for
    ("if a: pass\n", V310),
    ("if a:\n    pass\n", V310),
    ("if a:\n    b\nelse:\n    c\n", V310),
    ("if a:\n    b\nelif c:\n    d\n", V310),
    ("if a:\n    b\nelif c:\n    d\nelif e:\n    f\nelse:\n    g\n", V310),
    ("if a: b\nelse: c\n", V310),
    ("if a: b; c\n", V310),
    ("if a:\n    if b:\n        c\n    else:\n        d\n", V310),
    ("if a:\n    b\n\n\n    c\n", V310),
    ("if a:\n    b\n    # comment\nelse:\n    c\n", V310),
    ("while a:\n    b\n", V310),
    ("while a:\n    b\nelse:\n    c\n", V310),
    ("while a: pass\n", V310),
    ("while (a := f()):\n    pass\n", V310),
    ("for a in b:\n    c\n", V310),
    ("for a in b:\n    c\nelse:\n    d\n", V310),
    ("for a, b in c:\n    pass\n", V310),
    ("for (a, b) in c:\n    pass\n", V310),
    ("for a, in c:\n    pass\n", V310),
    ("for *a, b in c:\n    pass\n", V310),
    ("for a.b in c:\n    pass\n", V310),
    ("for a[0] in c:\n    pass\n", V310),
    ("for a in b, c:\n    pass\n", V310),
    ("for a in *b, c:\n    pass\n", V310),
    ("for a in b if c else d:\n    pass\n", V310),
    ("for a in range(10): print(a)\n", V310),
    (
        "async def f():\n    async for a in b:\n        pass\n    else:\n        pass\n",
        V310,
    ),
    # try / with
    ("try:\n    a\nexcept:\n    b\n", V310),
    ("try:\n    a\nexcept E:\n    b\n", V310),
    ("try:\n    a\nexcept E as e:\n    b\n", V310),
    ("try:\n    a\nexcept (E, F) as e:\n    b\n", V310),
    ("try:\n    a\nexcept E:\n    b\nexcept F:\n    c\n", V310),
    ("try:\n    a\nexcept E:\n    b\nelse:\n    c\n", V310),
    ("try:\n    a\nfinally:\n    b\n", V310),
    ("try:\n    a\nexcept E:\n    b\nelse:\n    c\nfinally:\n    d\n", V310),
    ("try: a\nexcept: b\n", V310),
    ("try:\n    a\nexcept* E:\n    b\n", V311),
    ("try:\n    a\nexcept* (E, F) as e:\n    b\nelse:\n    c\nfinally:\n    d\n", V311),
    ("try:\n    a\nexcept E, F:\n    b\n", V314),
    ("with a: pass\n", V310),
    ("with a:\n    b\n", V310),
    ("with a as b:\n    pass\n", V310),
    ("with a, b:\n    pass\n", V310),
    ("with a as b, c as d:\n    pass\n", V310),
    ("with a as (b, c):\n    pass\n", V310),
    ("with a as [b, c]:\n    pass\n", V310),
    ("with a as b.c:\n    pass\n", V310),
    ("with a as b[0]:\n    pass\n", V310),
    ("with (a):\n    pass\n", V310),
    ("with (a, b):\n    pass\n", V310),
    ("with (a as b):\n    pass\n", V310),
    ("with (a as b, c as d):\n    pass\n", V310),
    ("with (a as b, c as d,):\n    pass\n", V310),
    ("with (\n    a as b,\n    c as d,\n):\n    pass\n", V310),
    ("with (a) as b:\n    pass\n", V310),
    ("with (a, b) as c:\n    pass\n", V310),
    ("with (a)(b):\n    pass\n", V310),
    ("with (a).b as c:\n    pass\n", V310),
    ("with open(f) as g, open(h) as i:\n    pass\n", V310),
    ("async def f():\n    async with a as b, c:\n        pass\n", V310),
    # definitions
    ("def f(): pass\n", V310),
    ("def f():\n    pass\n", V310),
    ("def f(a): pass\n", V310),
    ("def f(a, b): pass\n", V310),
    ("def f(a, b,): pass\n", V310),
    ("def f(a=1): pass\n", V310),
    ("def f(a, b=2, c=3): pass\n", V310),
    ("def f(*a): pass\n", V310),
    ("def f(**a): pass\n", V310),
    ("def f(*a, **b): pass\n", V310),
    ("def f(a, *b, c, d=1, **e): pass\n", V310),
    ("def f(*, a): pass\n", V310),
    ("def f(*, a, b=1): pass\n", V310),
    ("def f(a, /): pass\n", V310),
    ("def f(a, /, b): pass\n", V310),
    ("def f(a, /, b, *, c): pass\n", V310),
    ("def f(a=1, /, b=2): pass\n", V310),
    ("def f(a, b=1, /, c=2, *d, e, f=3, **g): pass\n", V310),
    ("def f(a: int): pass\n", V310),
    ("def f(a: int = 1): pass\n", V310),
    ("def f(*a: int, **b: str): pass\n", V310),
    ("def f(a) -> int: pass\n", V310),
    ("def f() -> 'x': pass\n", V310),
    ("def f(a: 'x' = None, *, b: int) -> None: pass\n", V310),
    ("def f(\n    a,\n    b,\n): pass\n", V310),
    ("def f(a=lambda: 1): pass\n", V310),
    ("def f(a=(1, 2)): pass\n", V310),
    ("def f(a: int | None = None): pass\n", V310),
    ("def f(): return 1\n", V310),
    ("def f():\n    def g():\n        pass\n    return g\n", V310),
    ("@d\ndef f(): pass\n", V310),
    ("@d\n@e(1)\n@f.g\ndef h(): pass\n", V310),
    ("@(a if b else c)\ndef f(): pass\n", V310),
    ("@a[0]\ndef f(): pass\n", V310),
    ("async def f(): pass\n", V310),
    ("@d\nasync def f(): pass\n", V310),
    ("class A: pass\n", V310),
    ("class A:\n    pass\n", V310),
    ("class A(): pass\n", V310),
    ("class A(B): pass\n", V310),
    ("class A(B, C): pass\n", V310),
    ("class A(B, metaclass=M): pass\n", V310),
    ("class A(*B, **K): pass\n", V310),
    ("class A(metaclass=M, *B): pass\n", V310),
    ("@d\nclass A: pass\n", V310),
    ("class A:\n    x = 1\n    def f(self): pass\n    class B: pass\n", V310),
    ("class A:\n    '''doc'''\n    x: int = 1\n", V310),
    # generics and type aliases (3.12+)
    ("def f[T](a: T) -> T: pass\n", V312),
    ("def f[T: int, U: (int, str), *Ts, **P](a): pass\n", V312),
    ("class A[T]: pass\n", V312),
    ("class A[T](B[T]): pass\n", V312),
    ("type X = int\n", V312),
    ("type X[T] = list[T]\n", V312),
    ("type X[T: int, *Ts, **P] = Callable[P, T]\n", V312),
    ("async def f[T](): pass\n", V312),
    ("def f[T = int](): pass\n", V313),
    ("def f[**P = [int]](): pass\n", V313),
    ("type A = int; x = 1\n", V312),
    ("x = 1; type A = int\n", V312),
    ("if 1: type A = int\n", V312),
    ("type A = int; type B = str\n", V312),
    ("def f(*a: *tuple[int]): pass\n", V311),
    ("def f(*a: int, **k: str): pass\n", V310),
    ("x = a[*b if c else d]\n", V311),
    ("x = a[*b or c]\n", V311),
    ("x = a[*b, 1:2, *c]\n", V311),
    ("class A[*T = *tuple[int]]: pass\n", V313),
    ("class A[*T = int]: pass\n", V313),
    ("x = U'abc'\nx = u'abc'\nx = U'a' 'b'\n", V310),
    ("x = {(y := 1): 2}\n", V310),
    ("x = a[(y := 1):2]\n", V310),
    ("x = f'{a\n}'\n", V312),
    ('x = f"""{a\n}"""\n', V310),
    ("type = 1\n", V310),
    ("type(x)\n", V310),
    ("type.x = 1\n", V310),
    ("type: int = 1\n", V310),
    ("type[x] = 1\n", V310),
    ("print(type)\n", V310),
    # match statement
    ("match x:\n    case 1:\n        pass\n", V310),
    ("match x:\n    case 1:\n        pass\n    case _:\n        pass\n", V310),
    ("match x:\n    case 1 | 2 | 3:\n        pass\n", V310),
    ("match x:\n    case 'a':\n        pass\n    case b'b':\n        pass\n", V310),
    ("match x:\n    case 'a' 'b':\n        pass\n", V310),
    (
        "match x:\n    case None:\n        pass\n    case True:\n        pass\n    case False:\n        pass\n",
        V310,
    ),
    (
        "match x:\n    case -1:\n        pass\n    case 1.5:\n        pass\n    case -1.5:\n        pass\n",
        V310,
    ),
    ("match x:\n    case 1+2j:\n        pass\n    case -1-2j:\n        pass\n", V310),
    ("match x:\n    case a:\n        pass\n", V310),
    ("match x:\n    case a.b:\n        pass\n    case a.b.c:\n        pass\n", V310),
    ("match x:\n    case [a, b]:\n        pass\n", V310),
    ("match x:\n    case [a, b, *rest]:\n        pass\n", V310),
    ("match x:\n    case [*_, a]:\n        pass\n", V310),
    ("match x:\n    case []:\n        pass\n    case ():\n        pass\n", V310),
    ("match x:\n    case (a, b):\n        pass\n", V310),
    ("match x:\n    case (a,):\n        pass\n", V310),
    ("match x:\n    case a, b:\n        pass\n", V310),
    ("match x:\n    case a, *b:\n        pass\n", V310),
    ("match x:\n    case 1,:\n        pass\n", V310),
    ("match x:\n    case 1, if y:\n        pass\n", V310),
    ("match x:\n    case 1 | 2, if y:\n        pass\n", V310),
    ("match x:\n    case (a):\n        pass\n", V310),
    ("match x:\n    case (a | b):\n        pass\n", V310),
    ("match x:\n    case {}:\n        pass\n", V310),
    ("match x:\n    case {'a': 1}:\n        pass\n", V310),
    ("match x:\n    case {'a': 1, 'b': c, **rest}:\n        pass\n", V310),
    ("match x:\n    case {**rest}:\n        pass\n", V310),
    (
        "match x:\n    case {1: a, -2: b, None: c, True: d, A.B: e}:\n        pass\n",
        V310,
    ),
    ("match x:\n    case A():\n        pass\n", V310),
    ("match x:\n    case A(1, 2):\n        pass\n", V310),
    ("match x:\n    case A(a=1, b=c):\n        pass\n", V310),
    ("match x:\n    case A(1, b=2):\n        pass\n", V310),
    ("match x:\n    case A.B(1):\n        pass\n", V310),
    ("match x:\n    case A(B(C())):\n        pass\n", V310),
    ("match x:\n    case A(1,):\n        pass\n", V310),
    ("match x:\n    case a as b:\n        pass\n", V310),
    ("match x:\n    case [a, b] as c:\n        pass\n", V310),
    ("match x:\n    case 1 | 2 as c:\n        pass\n", V310),
    ("match x:\n    case (1 | 2) as c:\n        pass\n", V310),
    ("match x:\n    case a if a > 1:\n        pass\n", V310),
    ("match x:\n    case a if (b := a):\n        pass\n", V310),
    ("match x, y:\n    case 1, 2:\n        pass\n", V310),
    ("match (x, y):\n    case (1, 2):\n        pass\n", V310),
    ("match x,:\n    case (1,):\n        pass\n", V310),
    ("match *a, b:\n    case _:\n        pass\n", V310),
    ("match x := f():\n    case _:\n        pass\n", V310),
    ("match f(x):\n    case _:\n        pass\n", V310),
    ("match -x:\n    case _:\n        pass\n", V310),
    ("match [x]:\n    case _:\n        pass\n", V310),
    ("match x:\n    case 1: pass\n", V310),
    ("match x:\n    case 1:\n        a\n        b\n    case 2:\n        c\n", V310),
    ("match x:\n    case 1:\n        pass\n\n\n    case 2:\n        pass\n", V310),
    ("match x:\n    case A.B | C.D:\n        pass\n", V310),
    ("match x:\n    case 'a' | 'b':\n        pass\n", V310),
    (
        "def f():\n    match x:\n        case 1:\n            return 1\n    return 2\n",
        V310,
    ),
    (
        "match x:\n    case 1:\n        match y:\n            case 2:\n                pass\n",
        V310,
    ),
    # soft keywords as ordinary names
    ("match = 1\n", V310),
    ("match.x = 1\n", V310),
    ("match(x)\n", V310),
    ("match[x]\n", V310),
    ("match: int = 1\n", V310),
    ("match, case = 1, 2\n", V310),
    ("print(match, case)\n", V310),
    ("case = 1\ncase(x)\n", V310),
    ("match -1\n", V310),
    ("match (x)\n", V310),
    ("match * 2\n", V310),
    ("def match(): pass\n", V310),
    ("match = match + 1\n", V310),
    ("match if x else y\n", V310),
    ("match(x).y\n", V310),
    ("if match:\n    pass\n", V310),
    # layout
    ("\n\n\nx = 1\n\n\n", V310),
    ("# comment\nx = 1  # trailing\n# last\n", V310),
    ("x = (  # comment\n    1\n)\n", V310),
    ("x = [\n    1,  # one\n    2,\n]\n", V310),
    ("x = 1 + \\\n    2\n", V310),
    ("if a and \\\n   b:\n    pass\n", V310),
    ("def f():\n    pass\n\n\ndef g():\n    pass\n", V310),
    ("if a:\n  b\nelse:\n    c\n", V310),
    ("if a:\n\tb\n", V310),
    (
        "class A:\n    def f(self):\n        if a:\n            return 1\n        return 2\n    x = 1\n",
        V310,
    ),
    ("if 1:\n    if 2:\n        if 3:\n            pass\nx = 1\n", V310),
    ("x = 1\r\ny = 2\r\n", V310),
    ("\ufeffx = 1\n", V310),
    ("", V310),
    ("\n", V310),
    ("# only a comment", V310),
    ("   \n", V310),
    ("'''docstring'''\n", V310),
    ("def f():\n    '''doc'''\n", V310),
    ("if a:\n    pass\n    ", V310),
    ("if a:\n    pass\n  # dedented comment\nx = 1\n", V310),
    ("x = 'ünï'\n", V310),
    ("naïve = 1\n", V310),
    ("x = 'ሰላም'\n", V310),
]


def _python_accepts(source: str) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ast.parse(source.lstrip("\ufeff"))
    except (SyntaxError, ValueError):
        return False
    return True


@pytest.mark.parametrize(
    ("source", "since"), VALID, ids=[repr(s)[:60] for s, _ in VALID]
)
def test_matches_python_parser(source, since, plain_adapter):
    if sys.version_info < since:
        pytest.skip(f"needs Python {since[0]}.{since[1]}")
    if "\ufeff" in source or "ünï" in source or "naïve" in source or "ሰላም" in source:
        # Byte offsets differ from character offsets for non-ASCII text, so
        # compare structure only.
        expected = ast.parse(source.lstrip("\ufeff"))
        got = parse_with(source, plain_adapter)
        assert ast.dump(got) == ast.dump(expected)
        return
    assert_same_as_python(source, plain_adapter)


INVALID: list[tuple[str, tuple[int, int]]] = [
    ("x = \n", V310),
    ("= 1\n", V310),
    ("x = = 1\n", V310),
    ("1 = x\n", V310),
    ("'a' = x\n", V310),
    ("f() = 1\n", V310),
    ("a + b = 1\n", V310),
    ("None = 1\n", V310),
    ("True = 1\n", V310),
    ("(a, 1) = x\n", V310),
    ("[a, b()] = x\n", V310),
    ("a < b = 1\n", V310),
    ("x = 1 +\n", V310),
    ("x = (1\n", V310),
    ("x = 1)\n", V310),
    ("x = [1, 2\n", V310),
    ("x = {1: }\n", V310),
    ("x = {1: 2, 3}\n", V310),
    ("x = {1, 2: 3}\n", V310),
    ("x = (1 2)\n", V310),
    ("x = a b\n", V310),
    ("x = 1 2\n", V310),
    ("x = 'a' 1\n", V310),
    ("x = b'a' 'b'\n", V310),
    ("x = 0123\n", V310),
    ("x = 00123\n", V310),
    ("x = 1__0\n", V310),
    ("x = 1_\n", V310),
    ("x = 0b2\n", V310),
    ("x = 0xG\n", V310),
    ("x = (*a)\n", V310),
    ("x = [*a for a in b]\n", V310),
    ("x = {*a for a in b}\n", V310),
    ("x = (*a for a in b)\n", V310),
    ("x = {**a for a in b}\n", V310),
    ("x = [a for a in]\n", V310),
    ("x = [a for in b]\n", V310),
    ("x = [for a in b]\n", V310),
    ("x = [a async for a in b\n", V310),
    ("x = [a async x]\n", V310),
    ("x = lambda: \n", V310),
    ("x = lambda a=1, b: a\n", V310),
    ("x = lambda *: 1\n", V310),
    ("x = a if b\n", V310),
    ("x = a if else c\n", V310),
    ("x = if\n", V310),
    ("x = (y := )\n", V310),
    ("x = (1 := 2)\n", V310),
    ("x = (a.b := 2)\n", V310),
    ("x = not\n", V310),
    ("x = a not b\n", V310),
    ("x = a is not\n", V310),
    ("x = a[1:2:3:4]\n", V310),
    ("x = a[\n", V310),
    ("x = a.\n", V310),
    ("x = a.1\n", V310),
    ("x = a.if\n", V310),
    ("x = a..b\n", V310),
    ("f(\n", V310),
    ("f(a=)\n", V310),
    ("f(a=1, b)\n", V310),
    ("f(**k, a)\n", V310),
    ("f(**k, *a)\n", V310),
    ("f(x for x in y, 1)\n", V310),
    ("f(1, x for x in y)\n", V310),
    ("f(x for x in y for)\n", V310),
    ("f(if=1)\n", V310),
    ("f(a b)\n", V310),
    ("f(,)\n", V310),
    ("f(a,,)\n", V310),
    ("pass pass\n", V310),
    ("pass 1\n", V310),
    ("break 1\n", V310),
    ("return return\n", V310),
    ("if\n", V310),
    ("if :\n    pass\n", V310),
    ("if x\n    pass\n", V310),
    ("if x:\npass\n", V310),
    ("if x: if y: z\n", V310),
    ("if x:\n    pass\nelse\n", V310),
    ("else:\n    pass\n", V310),
    ("elif x:\n    pass\n", V310),
    ("if x:\n    pass\nelse:\n    pass\nelif y:\n    pass\n", V310),
    ("if x:\n    pass\nelse if y:\n    pass\n", V310),
    ("while:\n    pass\n", V310),
    ("while x:\n", V310),
    ("while x\n    pass\n", V310),
    ("for in b:\n    pass\n", V310),
    ("for a b:\n    pass\n", V310),
    ("for a in:\n    pass\n", V310),
    ("for 1 in b:\n    pass\n", V310),
    ("for f() in b:\n    pass\n", V310),
    ("for a in b\n    pass\n", V310),
    ("try:\n    pass\n", V310),
    ("try:\n    pass\nelse:\n    pass\n", V310),
    ("try:\n    pass\nexcept E as 1:\n    pass\n", V310),
    ("try:\n    pass\nexcept E as:\n    pass\n", V310),
    ("try\n    pass\nexcept:\n    pass\n", V310),
    ("try:\n    pass\nfinally\n    pass\n", V310),
    ("except E:\n    pass\n", V310),
    ("finally:\n    pass\n", V310),
    ("with:\n    pass\n", V310),
    ("with a as:\n    pass\n", V310),
    ("with a as 1:\n    pass\n", V310),
    ("with a, :\n    pass\n", V310),
    ("with (a as b\n    pass\n", V310),
    ("with a\n    pass\n", V310),
    ("def\n", V310),
    ("def f:\n    pass\n", V310),
    ("def f(:\n    pass\n", V310),
    ("def f():\n", V310),
    ("def f()\n    pass\n", V310),
    ("def f(a, a=1, b): pass\n", V310),
    ("def f(a=1, b): pass\n", V310),
    ("def f(*): pass\n", V310),
    ("def f(*, **k): pass\n", V310),
    ("def f(*,): pass\n", V310),
    ("def f(**k, a): pass\n", V310),
    ("def f(**k, **j): pass\n", V310),
    ("def f(*a, *b): pass\n", V310),
    ("def f(/): pass\n", V310),
    ("def f(a, /, /): pass\n", V310),
    ("def f(*, /): pass\n", V310),
    ("def f(*a, /): pass\n", V310),
    ("def f(1): pass\n", V310),
    ("def f(a b): pass\n", V310),
    ("def f(a: ): pass\n", V310),
    ("def f(a) -> : pass\n", V310),
    ("def if(): pass\n", V310),
    ("def f(if): pass\n", V310),
    ("def f(None): pass\n", V310),
    ("def f(a.b): pass\n", V310),
    ("def f(self, (a, b)): pass\n", V310),
    ("def f(a=): pass\n", V310),
    ("class\n", V310),
    ("class A\n    pass\n", V310),
    ("class A(:\n    pass\n", V310),
    ("class A(x for x in y): pass\n", V310),
    ("class 1: pass\n", V310),
    ("class A:\n", V310),
    ("@d\nx = 1\n", V310),
    ("@d\n", V310),
    ("@\ndef f(): pass\n", V310),
    ("@d x\ndef f(): pass\n", V310),
    ("@d\n\nx = 1\n", V310),
    ("async x = 1\n", V310),
    ("async\n", V310),
    ("async if x: pass\n", V310),
    ("async class A: pass\n", V310),
    ("@d\nasync class A: pass\n", V310),
    ("import\n", V310),
    ("import a.\n", V310),
    ("import .a\n", V310),
    ("import a as\n", V310),
    ("import a as 1\n", V310),
    ("import a b\n", V310),
    ("import a,\n", V310),
    ("import (a)\n", V310),
    ("import *\n", V310),
    ("from\n", V310),
    ("from a\n", V310),
    ("from a import\n", V310),
    ("from import a\n", V310),
    ("from a import (b\n", V310),
    ("from a import b,\n", V310),
    ("from a import (b c)\n", V310),
    ("from a import *, b\n", V310),
    ("from a import (*)\n", V310),
    ("from a import b as\n", V310),
    ("from a.b. import c\n", V310),
    ("from .. import\n", V310),
    ("global\n", V310),
    ("global 1\n", V310),
    ("global a,\n", V310),
    ("nonlocal\n", V310),
    ("del\n", V310),
    ("del 1\n", V310),
    ("del f()\n", V310),
    ("del a + b\n", V310),
    ("del (a, 1)\n", V310),
    ("del a,,\n", V310),
    ("assert\n", V310),
    ("assert x,\n", V310),
    ("raise from x\n", V310),
    ("raise x from\n", V310),
    ("yield = 1\n", V310),
    ("x = yield yield\n", V310),
    ("x += \n", V310),
    ("x += y += 1\n", V310),
    ("(a, b) += 1\n", V310),
    ("[a] += 1\n", V310),
    ("f() += 1\n", V310),
    ("1 += 1\n", V310),
    ("a, b += 1\n", V310),
    ("x: \n", V310),
    ("x: int =\n", V310),
    ("a, b: int\n", V310),
    ("[a]: int\n", V310),
    ("f(): int\n", V310),
    ("x: int = 1 = 2\n", V310),
    ("lambda\n", V310),
    ("(yield\n", V310),
    ("match x:\n    case 1:\n", V310),
    ("match x:\n    pass\n", V310),
    ("match x:\n    case:\n        pass\n", V310),
    ("match x:\n    case 1\n        pass\n", V310),
    ("match x:\n    case 1:\npass\n", V310),
    ("match x:\n    case *a:\n        pass\n", V310),
    (
        "match x:\n    case a.b():\n        pass\n    case 1():\n        pass\n",
        V310,
    ),
    ("match x:\n    case A(a=1, 2):\n        pass\n", V310),
    ("match x:\n    case {1: a, **r, 2: b}:\n        pass\n", V310),
    ("match x:\n    case {a: 1}:\n        pass\n", V310),
    ("match x:\n    case 1 as _:\n        pass\n", V310),
    ("match x:\n    case -a:\n        pass\n", V310),
    ("match x:\n    case 1+:\n        pass\n", V310),
    ("match x:\n    case [1,, 2]:\n        pass\n", V310),
    ("match x:\n    case (1:\n        pass\n", V310),
    ("match x:\n    case {1: 2:\n        pass\n", V310),
    ("match x:\n    case a | :\n        pass\n", V310),
    ("match x:\n    case 1:\n        pass\n    x = 1\n", V310),
    ("match x:\n    case 1 if:\n        pass\n", V310),
    ("match *a:\n    case _:\n        pass\n", V310),
    ("match x:\n    case ):\n        pass\n", V310),
    ("match x: pass\n", V310),
    ("match x:\n    case {[1]: a}:\n        pass\n", V310),
    ("type X = int int\n", V312),
    ("del (*a,)\n", V310),
    ("del *a\n", V310),
    ("x = {y := 1: 2}\n", V310),
    ("x = a[y := 1:2]\n", V310),
    ("match x:\n    case 1 + 2:\n        pass\n", V310),
    ("match x:\n    case 1j + 2:\n        pass\n", V310),
    ("match x:\n    case 1 + 2.5:\n        pass\n", V310),
    ("match x:\n    case 1 - a:\n        pass\n", V310),
    ("match x:\n    case {**_}:\n        pass\n", V310),
    ("match x:\n    case (*y):\n        pass\n", V310),
    ("try:\n    pass\nexcept* A:\n    pass\nexcept B:\n    pass\n", V311),
    ("try:\n    pass\nexcept A:\n    pass\nexcept* B:\n    pass\n", V311),
    ("try:\n    pass\nexcept*:\n    pass\n", V311),
    ("try:\n    pass\nexcept A, B as c:\n    pass\n", V314),
    ("from __future__ import nope\n", V314),
    ("from __future__ import braces\n", V314),
    ("def f(*a: *b): pass\n", V310),
    ("def f(*a: **b): pass\n", V310),
    ("  x = 1\n", V310),
    ("x = 1\n  y = 2\n", V310),
    ("if x:\n    a\n  b\n", V310),
    ("if x:\n        a\n    b\n", V310),
    ("if x:\n    a\n        b\n", V310),
    ("\tx = 1\n", V310),
    ("x = 'a\n", V310),
    ("x = '''a\n", V310),
    ("x = \"a'\n", V310),
    ("x = $\n", V310),
    ("x = ?\n", V310),
    ("x = a ! b\n", V310),
    ("x = 'a' f'{'\n", V310),
    ("x = f'{}'\n", V310),
    ("x = f'{a!x}'\n", V310),
    ("x = f'{a'\n", V310),
    ("x = f'a}'\n", V310),
    ("x = f'{a b}'\n", V310),
    ("x = f'{!r}'\n", V310),
    ("x = f'{a:{}}'\n", V310),
    ("x = ... ...\n", V310),
    ("x = 1 if 2 else\n", V310),
    ("x = a if b else c d\n", V310),
    ("x = [1 2]\n", V310),
    ("x = [1,, 2]\n", V310),
    ("x = (,)\n", V310),
    ("x = [,]\n", V310),
    ("x = {,}\n", V310),
    ("x = a[,]\n", V310),
    ("x = a[1,,2]\n", V310),
    ("x = a[:::]\n", V310),
    ("x = *\n", V310),
    ("x = **a\n", V310),
    ("x = a ** \n", V310),
    ("x = a **\n", V310),
    ("x = await\n", V310),
    ("x = -\n", V310),
    ("x = ~\n", V310),
    ("x = a @\n", V310),
    ("x = a //\n", V310),
    ("x = a <\n", V310),
    ("x = a ==\n", V310),
    ("x = a and\n", V310),
    ("x = a or\n", V310),
    ("x = and a\n", V310),
    ("x = or a\n", V310),
    ("x = in a\n", V310),
    ("x = is a\n", V310),
    ("x = a in\n", V310),
    ("x = else\n", V310),
    ("x = for\n", V310),
    ("x = while\n", V310),
    ("x = class\n", V310),
    ("x = def\n", V310),
    ("x = import\n", V310),
    ("x = pass\n", V310),
    ("x = return\n", V310),
    ("x = del\n", V310),
    ("x = global\n", V310),
    ("x = try\n", V310),
    ("x = with\n", V310),
    ("x = as\n", V310),
    ("x = from\n", V310),
    ("x = async\n", V310),
    ("x = :\n", V310),
    ("x = ;\n", V310),
    ("x = ->\n", V310),
    (": x\n", V310),
    (", x\n", V310),
    (") x\n", V310),
    ("] x\n", V310),
    ("} x\n", V310),
    ("-> x\n", V310),
    (".\n", V310),
    ("...x\n", V310),
    (";\n", V310),
    ("x ;; y\n", V310),
    ("x = 1;; y\n", V310),
]


@pytest.mark.parametrize(
    ("source", "since"), INVALID, ids=[repr(s)[:60] for s, _ in INVALID]
)
def test_rejects_what_python_rejects(source, since, plain_adapter):
    if sys.version_info < since:
        pytest.skip(f"needs Python {since[0]}.{since[1]}")
    if _python_accepts(source):
        pytest.skip("this Python version accepts it")
    with pytest.raises(OrmError) as exc:
        parse_with(source, plain_adapter)
    assert exc.value.code in ("E0001", "E0010")
    assert exc.value.orm_line >= 1


class TestErrorDetails:
    def test_syntax_error_has_line_column_and_text(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("a = 1\nb = = 2\n", plain_adapter)
        err = exc.value
        assert err.code == "E0010"
        assert err.orm_line == 2
        assert err.orm_col == 5
        assert err.context["text"] == "b = = 2"

    def test_error_on_last_line_without_newline(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = 1 +", plain_adapter)
        assert exc.value.orm_line == 1

    def test_unexpected_indent_message(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = 1\n    y = 2\n", plain_adapter)
        assert "indent" in exc.value.message

    def test_missing_block_message(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("if x:\npass\n", plain_adapter)
        assert "indented block" in exc.value.message
        assert exc.value.orm_line == 2

    def test_assign_to_call_message(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("f() = 1\n", plain_adapter)
        assert "call" in exc.value.message

    def test_error_inside_f_string_is_reported(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = 1\ny = f'{a b}'\n", plain_adapter)
        assert exc.value.orm_line == 2

    def test_invalid_string_escape_is_reported(self, plain_adapter):
        with pytest.raises(OrmSyntaxError):
            parse_with("x = '\\N{NOT A REAL NAME}'\n", plain_adapter)

    def test_error_names_the_language(self, oromo_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("yoo :\n", oromo_adapter)
        assert exc.value.lang == "afan_oromo"

    def test_deeply_nested_input_fails_cleanly_or_parses(self, plain_adapter):
        source = "x = " + "(" * 50 + "1" + ")" * 50 + "\n"
        assert_same_as_python(source, plain_adapter)


class TestPositions:
    def test_name_positions(self, plain_adapter):
        tree = parse_with("abc = 12\n", plain_adapter)
        assign = tree.body[0]
        assert (assign.lineno, assign.col_offset) == (1, 0)
        assert (assign.end_lineno, assign.end_col_offset) == (1, 8)
        assert assign.targets[0].end_col_offset == 3
        assert assign.value.col_offset == 6

    def test_compound_statement_ends_at_last_body_token(self, plain_adapter):
        tree = parse_with("if a:\n    b = 1\n\n\nc\n", plain_adapter)
        node = tree.body[0]
        assert (node.lineno, node.end_lineno) == (1, 2)
        assert node.end_col_offset == 9

    def test_parenthesised_binary_operation_starts_at_the_bracket(self, plain_adapter):
        tree = parse_with("x = (a + b) * c\n", plain_adapter)
        outer = tree.body[0].value
        assert outer.col_offset == 4
        assert outer.left.col_offset == 5

    def test_decorated_function_starts_at_def(self, plain_adapter):
        tree = parse_with("@d\ndef f(): pass\n", plain_adapter)
        assert tree.body[0].lineno == 2
        assert tree.body[0].decorator_list[0].lineno == 1

    def test_generator_argument_spans_the_call_brackets(self, plain_adapter):
        tree = parse_with("f(x for x in y)\n", plain_adapter)
        gen = tree.body[0].value.args[0]
        assert (gen.col_offset, gen.end_col_offset) == (1, 15)

    def test_positions_use_original_text_after_translation(self, oromo_adapter):
        tree = parse_with("agarsiisi(1)\n", oromo_adapter)
        call = tree.body[0].value
        assert call.func.end_col_offset == 9
        assert call.end_col_offset == 12

    def test_multi_line_string_position(self, plain_adapter):
        tree = parse_with("x = '''a\nb'''\n", plain_adapter)
        value = tree.body[0].value
        assert (value.lineno, value.end_lineno) == (1, 2)


class TestOromoSource:
    def test_hello_world(self, oromo_adapter):
        tree = parse_with('agarsiisi("Akkam!")\n', oromo_adapter)
        assert ast.unparse(tree) == "print('Akkam!')"

    def test_function_and_class(self, oromo_adapter):
        source = (
            "gosa Barataa:\n"
            "    hojii __init__(of, maqaa):\n"
            "        of.maqaa = maqaa\n"
        )
        tree = parse_with(source, oromo_adapter)
        assert ast.unparse(tree).startswith("class Barataa:")
        assert "self.maqaa = maqaa" in ast.unparse(tree)

    def test_match_statement(self, oromo_adapter):
        source = (
            "walsimsiisi x:\n"
            "    haala 1:\n"
            "        deebi 'a'\n"
            "    haala _:\n"
            "        deebi 'b'\n"
        )
        tree = parse_with(source, oromo_adapter)
        assert isinstance(tree.body[0], ast.Match)
        assert len(tree.body[0].cases) == 2

    def test_match_as_ordinary_name_in_oromo(self, oromo_adapter):
        tree = parse_with("walsimsiisi = 1\n", oromo_adapter)
        assert isinstance(tree.body[0], ast.Assign)

    def test_elif_else_chain(self, oromo_adapter):
        source = "yoo a:\n    darbii\nyookaan b:\n    darbii\nyoo_miti:\n    darbii\n"
        tree = parse_with(source, oromo_adapter)
        assert ast.unparse(tree).count("elif") == 1
        assert "else:" in ast.unparse(tree)

    def test_try_except_finally(self, oromo_adapter):
        source = "yaali:\n    a\ndogoggora E akka e:\n    b\ndhuma:\n    c\n"
        tree = parse_with(source, oromo_adapter)
        assert isinstance(tree.body[0], ast.Try)

    def test_f_string_with_oromo_names(self, oromo_adapter):
        tree = parse_with("f'{of.maqaa}: {of.umri}'\n", oromo_adapter)
        assert ast.unparse(tree) == "f'{self.maqaa}: {self.umri}'"

    def test_all_examples_parse(self, oromo_adapter):
        from pathlib import Path

        examples = Path(__file__).parent.parent / "examples"
        files = sorted(examples.glob("*.orm"))
        assert files
        for path in files:
            parse_with(path.read_text(encoding="utf-8"), oromo_adapter)


class TestGrammarHooks:
    class _Hooks:
        @staticmethod
        def pre_parse(source: str) -> str:
            return source.replace("ONE", "1")

    class _Identity:
        @staticmethod
        def pre_parse(source: str) -> str:
            return source

    def _adapter(self, hooks) -> Adapter:
        return Adapter(
            lang="hooked",
            keyword_map={},
            builtin_map={},
            error_messages={},
            grammar_hooks=hooks,  # type: ignore[arg-type]
        )

    def test_hook_that_changes_text_is_applied(self):
        adapter = self._adapter(self._Hooks)
        tree = parse_with("x = ONE\n", adapter)
        assert ast.unparse(tree) == "x = 1"

    def test_identity_hook_uses_the_normal_path(self):
        adapter = self._adapter(self._Identity)
        assert_same_as_python("x = [1, 2]\n", adapter)

    def test_hook_result_with_syntax_error(self):
        class Bad:
            @staticmethod
            def pre_parse(source: str) -> str:
                return "x = = 1\n"

        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = 1\n", self._adapter(Bad))
        assert exc.value.code == "E0010"

    def test_module_without_pre_parse(self):
        import types

        adapter = self._adapter(types.ModuleType("empty"))
        assert_same_as_python("x = 1\n", adapter)


class TestAgainstStandardLibrary:
    """Parse real code and compare with CPython's own parser."""

    # Python 3.14 template strings are not supported.
    SKIP = {"annotationlib.py", "templatelib.py"}

    def _files(self) -> list[str]:
        root = sysconfig.get_paths()["stdlib"]
        files = sorted(glob.glob(f"{root}/*.py"))
        return [f for f in files if f.rsplit("/", 1)[-1] not in self.SKIP]

    def test_sample_of_standard_library(self, plain_adapter):
        files = self._files()
        if not files:
            pytest.skip("standard library sources are not available")
        checked = 0
        for path in files[::6]:
            source = open(path, encoding="utf-8").read()  # noqa: SIM115
            if not source.isascii() or "\r" in source:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ast.parse(source)
            except SyntaxError:
                continue
            assert_same_as_python(source, plain_adapter)
            checked += 1
        assert checked > 10

    @pytest.mark.slow
    def test_whole_standard_library(self, plain_adapter):
        root = sysconfig.get_paths()["stdlib"]
        files = sorted(glob.glob(f"{root}/**/*.py", recursive=True))
        if not files:
            pytest.skip("standard library sources are not available")
        failures = []
        checked = 0
        for path in files:
            if path.rsplit("/", 1)[-1] in self.SKIP:
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
            except (UnicodeDecodeError, OSError):
                continue
            if "\r" in source or "\x00" in source:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    expected = ast.parse(source)
            except (SyntaxError, ValueError, RecursionError):
                continue
            checked += 1
            try:
                got = parse_with(source, plain_adapter)
            except OrmError as exc:
                failures.append(f"{path}: {exc}")
                continue
            if ast.dump(got) != ast.dump(expected):
                failures.append(f"{path}: different tree")
            elif source.isascii() and positions(got) != positions(expected):
                failures.append(f"{path}: different positions")
        assert checked > 100
        assert not failures, failures[:5]


class TestEdgeCases:
    def test_token_list_without_endmarker(self, plain_adapter):
        tokens = [
            t
            for t in OrmLexer("x = 1\n", plain_adapter).tokenize()
            if t.type != tokenize.ENDMARKER
        ]
        tree = OrmParser(plain_adapter).parse(tokens)
        assert ast.dump(tree) == ast.dump(ast.parse("x = 1\n"))

    def test_empty_token_list(self, plain_adapter):
        tree = OrmParser(plain_adapter).parse([])
        assert ast.dump(tree) == ast.dump(ast.parse(""))

    def test_stray_newline_tokens_are_skipped(self, plain_adapter):
        newline = tokenize.TokenInfo(tokenize.NEWLINE, "\n", (1, 0), (1, 1), "\n")
        tokens = [newline, *OrmLexer("x = 1\n", plain_adapter).tokenize()]
        tree = OrmParser(plain_adapter).parse(tokens)
        assert ast.dump(tree) == ast.dump(ast.parse("x = 1\n"))

    def test_stray_newline_token_inside_a_block(self, plain_adapter):
        tokens = OrmLexer("if a:\n    b\n", plain_adapter).tokenize()
        index = next(i for i, t in enumerate(tokens) if t.type == tokenize.INDENT)
        newline = tokenize.TokenInfo(tokenize.NEWLINE, "\n", (2, 0), (2, 1), "\n")
        tokens.insert(index + 1, newline)
        tree = OrmParser(plain_adapter).parse(tokens)
        assert ast.dump(tree) == ast.dump(ast.parse("if a:\n    b\n"))

    def test_too_many_digits_in_integer(self, plain_adapter):
        limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
        if limit == 0:
            pytest.skip("this Python has no integer digit limit")
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x = " + "9" * (limit + 1) + "\n", plain_adapter)
        assert "invalid number" in exc.value.message

    def test_identifiers_are_normalised_like_python(self, plain_adapter):
        source = "\uff58 = 1\n\ufb01 = \uff58\nprint(fi)\n"
        assert ast.dump(parse_with(source, plain_adapter)) == ast.dump(
            ast.parse(source)
        )

    def test_float_overflow_is_infinity_like_python(self, plain_adapter):
        assert_same_as_python("x = 1e999\n", plain_adapter)

    def test_octal_hex_binary_values(self, plain_adapter):
        tree = parse_with("x = 0o17 + 0xFf + 0b101 + 0_0 + 1_0\n", plain_adapter)
        values = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)]
        assert sorted(values) == [0, 5, 10, 15, 255]

    def test_u_prefix_sets_kind(self, plain_adapter):
        tree = parse_with("x = u'a'\n", plain_adapter)
        assert tree.body[0].value.kind == "u"
        tree = parse_with("x = 'a'\n", plain_adapter)
        assert tree.body[0].value.kind is None

    @pytest.mark.parametrize(
        "source", ["x = kennii_irra\n", "x = 1 + kennii_irra\n", "f(kennii_irra)\n"]
    )
    def test_yield_from_word_needs_a_value(self, source, oromo_adapter):
        with pytest.raises(OrmSyntaxError):
            parse_with(source, oromo_adapter)

    def test_yield_from_translated_keyword(self, oromo_adapter):
        tree = parse_with("hojii g():\n    kennii_irra h()\n", oromo_adapter)
        assert isinstance(tree.body[0].body[0].value, ast.YieldFrom)

    def test_yield_followed_by_from_as_two_tokens(self, plain_adapter):
        assert_same_as_python("def g():\n    yield from h()\n", plain_adapter)

    def test_type_parameters_need_new_python(self, plain_adapter, monkeypatch):
        monkeypatch.setattr(parser_module, "_HAS_TYPE_PARAMS", False)
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("def f[T](): pass\n", plain_adapter)
        assert "3.12" in exc.value.message

    def test_type_alias_is_a_plain_name_on_old_python(self, plain_adapter, monkeypatch):
        monkeypatch.setattr(parser_module, "_HAS_TYPE_PARAMS", False)
        with pytest.raises(OrmSyntaxError):
            parse_with("type X = int\n", plain_adapter)
        assert_same_as_python("type = 1\n", plain_adapter)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="needs 3.12 syntax")
    def test_type_parameter_defaults_need_python_313(self, plain_adapter, monkeypatch):
        monkeypatch.setattr(parser_module, "_HAS_TYPE_PARAM_DEFAULTS", False)
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("def f[T = int](): pass\n", plain_adapter)
        assert "3.13" in exc.value.message

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="needs 3.11 syntax")
    def test_except_star_needs_python_311(self, plain_adapter, monkeypatch):
        monkeypatch.delattr(ast, "TryStar")
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("try:\n    a\nexcept* E:\n    b\n", plain_adapter)
        assert "3.11" in exc.value.message

    def test_starred_subscript_follows_the_python_version(self, plain_adapter):
        source = "x[*a, *b]\n"
        if sys.version_info >= (3, 11):
            assert_same_as_python(source, plain_adapter)
        else:
            with pytest.raises(OrmSyntaxError):
                parse_with(source, plain_adapter)

    def test_starred_annotation_needs_python_311(self, plain_adapter, monkeypatch):
        monkeypatch.setattr(parser_module, "_STAR_IN_SUBSCRIPT", False)
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("def f(*a: *b): pass\n", plain_adapter)
        assert "3.11" in exc.value.message

    def test_starred_subscript_needs_python_311(self, plain_adapter, monkeypatch):
        monkeypatch.setattr(parser_module, "_STAR_IN_SUBSCRIPT", False)
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("x[*a]\n", plain_adapter)
        assert "3.11" in exc.value.message

    def test_empty_type_parameter_list_is_an_error(self, plain_adapter):
        if sys.version_info < (3, 12):
            pytest.skip("needs 3.12 syntax")
        for source in ("def f[](): pass\n", "class A[]: pass\n", "type X[] = int\n"):
            with pytest.raises(OrmSyntaxError):
                parse_with(source, plain_adapter)

    def test_invalid_escape_warning_points_at_the_orm_line(self, plain_adapter):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parse_with("x = 1\ny = '\\d'\n", plain_adapter)
        assert [(w.filename, w.lineno) for w in caught] == [("<orm>", 2)]

    def test_valid_escapes_do_not_warn(self, plain_adapter):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parse_with("x = '\\n\\t\\\\' + r'\\d'\n", plain_adapter)
        assert caught == []

    def test_unparenthesised_except_tuple_follows_the_python_version(
        self, plain_adapter
    ):
        source = "try:\n    a\nexcept E, F:\n    b\n"
        if sys.version_info >= (3, 14):
            assert_same_as_python(source, plain_adapter)
        else:
            with pytest.raises(OrmSyntaxError):
                parse_with(source, plain_adapter)

    def test_ellipsis_and_not_implemented_style_names(self, plain_adapter):
        assert_same_as_python("x = ...\ny = NotImplemented\n", plain_adapter)

    def test_constants_cannot_be_assigned(self, plain_adapter):
        for name in ("None", "True", "False"):
            with pytest.raises(OrmSyntaxError):
                parse_with(f"{name} = 1\n", plain_adapter)

    def test_keywords_cannot_be_names(self, plain_adapter):
        for word in ("if", "class", "def", "lambda", "yield", "await", "async"):
            with pytest.raises(OrmSyntaxError):
                parse_with(f"{word} = 1\n", plain_adapter)

    def test_parser_object_is_reusable(self, plain_adapter):
        parser = OrmParser(plain_adapter)
        first = parser.parse(OrmLexer("x = 1\n", plain_adapter).tokenize())
        second = parser.parse(OrmLexer("y = 2\n", plain_adapter).tokenize())
        assert ast.unparse(first) == "x = 1"
        assert ast.unparse(second) == "y = 2"

    def test_failed_parse_does_not_break_the_next_one(self, plain_adapter):
        parser = OrmParser(plain_adapter)
        with pytest.raises(OrmSyntaxError):
            parser.parse(OrmLexer("x = = 1\n", plain_adapter).tokenize())
        tree = parser.parse(OrmLexer("x = 1\n", plain_adapter).tokenize())
        assert ast.unparse(tree) == "x = 1"

    def test_returned_module_is_compilable(self, plain_adapter):
        source = "def f(a, *b, c=1, **d):\n    return [a, b, c, d]\n"
        tree = parse_with(source, plain_adapter)
        ast.fix_missing_locations(tree)
        namespace: dict[str, object] = {}
        exec(compile(tree, "<test>", "exec"), namespace)  # noqa: S102
        assert namespace["f"](1, 2, c=3, e=4) == [1, (2,), 3, {"e": 4}]

    def test_if_elif_chain(self, plain_adapter):
        lines = ["if x == 0:", "    pass"]
        for n in range(1, 60):
            lines += [f"elif x == {n}:", "    pass"]
        assert_same_as_python("\n".join(lines) + "\n", plain_adapter)

    def test_very_long_elif_chain_parses(self, plain_adapter):
        lines = ["if x == 0:", "    pass"]
        for n in range(1, 400):
            lines += [f"elif x == {n}:", "    pass"]
        tree = parse_with("\n".join(lines) + "\n", plain_adapter)
        depth = 0
        node = tree.body[0]
        while node.orelse:
            node = node.orelse[0]
            depth += 1
        assert depth == 399

    def test_many_statements(self, plain_adapter):
        assert_same_as_python("x = 1\n" * 5000, plain_adapter)

    def test_deep_nesting_of_blocks(self, plain_adapter):
        lines = [f"{'    ' * i}if x:" for i in range(40)]
        lines.append(f"{'    ' * 40}pass")
        assert_same_as_python("\n".join(lines) + "\n", plain_adapter)

    def test_chained_attribute_and_call_depth(self, plain_adapter):
        assert_same_as_python("x = a" + ".b(1)" * 200 + "\n", plain_adapter)

    def test_wide_expression(self, plain_adapter):
        assert_same_as_python("x = " + " + ".join(["a"] * 500) + "\n", plain_adapter)


LAYOUT_CASES = [
    # backslash continuations
    "x = 1 \\\n# c",
    "x = 1 \\\n# c\n",
    "x = 1 \\\n   ",
    "x = 1 \\\n\t",
    "x = 1 \\\n\n",
    "x = 1 \\\n   \n",
    "x = 1 \\",
    "x = 1 \\\n",
    "\\\n",
    "\\\n\\\n",
    "\\\n   ",
    "\\\nx = 1\n",
    "    \\\nx = 1\n",
    "x = 1\n\\\n",
    "x = 1\n\\\n   ",
    "x = 1\n  \\\n",
    "if 1:\n    a\n\\\n    b\n",
    "if 1:\n    a\n\\\nb\n",
    "if 1:\n    a\n  \\\n    b\n",
    "if 1:\n    a\n  \\\nb\n",
    "if 1:\n    a\n    \\\n  b\n",
    "if 1:\n    a\n \\\n\\\n    b\n",
    "if 1:\n    a\n\\\n \\\n    b\n",
    "if 1:\n    a\n\f \\\n    b\n",
    "if 1:\n  x \\\n\n  y\n",
    "match x:\n\\\n\\\n \\\n\f    case 1:\n        pass\n",
    "x = (1 \\\n)",
    "@\\\nd\ndef f(): pass",
    # tabs and spaces
    "if 1:\n\tx\n\ty\n",
    "if 1:\n\tx\n        y\n",
    "if 1:\n        x\n\ty\n",
    "if 1:\n    x\n\ty\n",
    "if 1:\n\tx\n    y\n",
    "if 1:\n \tx\n\ty\n",
    "if 1:\n\tx\n \ty\n",
    "if 1:\n  if 2:\n\tx\n  y\n",
    "if 1:\n\tif 2:\n\t\tx\n\ty\n",
    "if 1:\n  x\n\n\t\n  y\n",
    "if 1:\n x\n\f\ty\n",
    "\tx = 1\n",
    " x = 1\n",
    "x = 1\n y = 2\n",
    "if 1:\n x\n  y\n",
    # form feeds and blank lines
    "\fx = 1\n",
    "x\f= 1\n",
    "if 1:\n x\n\f y\n",
    "x = 1\n\v",
    "pass\n  \n",
    "pass\n\t\n",
    "if 1:\n  pass\n \n  pass\n",
    "if 1:\n    pass\n  # dedented comment\nx = 1\n",
    # null and control characters
    "x = 1  # c\x00",
    "\x00",
    "a\x00b",
    "x = '\x00'",
    "x = 1\x1a",
    "x = '\x1a'",
    "x = 1\u00a0+ 2",
    "# \u2028 comment\nx = 1\n",
    # line endings
    "x = 1\r\ny = 2\r\n",
    "x = 1\ry = 2\r",
    "if 1:\r\n    x\r\n",
    "x = '''a\r\nb'''\r\n",
    # unterminated things
    "x = '''a",
    'x = """a"b\n',
    'x = """ "\n',
    "x = (1,\n",
    "x = [1,\n  2\n",
    "x = {\n",
    "x = 'a\n",
    "x = f'{a'\n",
    "def f(:\n    pass\n",
]


@pytest.mark.parametrize(
    "source", LAYOUT_CASES, ids=[repr(s)[:50] for s in LAYOUT_CASES]
)
def test_layout_cases_agree_with_python(source, plain_adapter):
    if _python_accepts(source):
        assert_same_as_python(source, plain_adapter)
    else:
        with pytest.raises(OrmError):
            parse_with(source, plain_adapter)


class TestReviewFixes:
    def test_deep_brackets_raise_a_clean_error(self, plain_adapter):
        source = "x = " + "(" * 20000 + "1" + ")" * 20000 + "\n"
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with(source, plain_adapter)
        assert "nesting" in exc.value.message
        assert exc.value.orm_line == 1

    @pytest.mark.parametrize("open_text", ["(", "[", "f(", "{1: ", "a[", "-", "not "])
    def test_each_kind_of_deep_nesting_raises_a_clean_error(
        self, open_text, plain_adapter
    ):
        closers = {"(": ")", "[": "]", "f(": ")", "{1: ": "}", "a[": "]"}
        source = "x = " + open_text * 5000 + "1" + closers.get(open_text, "") * 5000
        with pytest.raises(OrmError):
            parse_with(source + "\n", plain_adapter)

    def test_deep_nesting_of_blocks_raises_a_clean_error(self, plain_adapter):
        lines = [f"{' ' * i}if x:" for i in range(3000)]
        lines.append(" " * 3000 + "pass")
        with pytest.raises(OrmError):
            parse_with("\n".join(lines) + "\n", plain_adapter)

    def test_moderate_nesting_still_works(self, plain_adapter):
        assert_same_as_python("x = " + "(" * 40 + "1" + ")" * 40 + "\n", plain_adapter)

    @pytest.mark.parametrize(
        ("source", "line", "text"),
        [
            ("if x:\n", 1, "if x:"),
            ("x = 1\nif x:\n", 2, "if x:"),
            ("def f():\n    if x:\n", 2, "    if x:"),
            ("x = (1 +", 1, "x = (1 +"),
            ("class A:", 1, "class A:"),
            ("x = 1 +\n", 1, "x = 1 +"),
        ],
    )
    def test_error_at_end_of_input_points_at_the_last_real_line(
        self, source, line, text, plain_adapter
    ):
        with pytest.raises(OrmError) as exc:
            parse_with(source, plain_adapter)
        assert exc.value.orm_line == line
        assert exc.value.context.get("text", text) == text

    def test_error_at_end_of_input_column_is_after_the_last_token(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as exc:
            parse_with("if x:\n", plain_adapter)
        assert (exc.value.orm_line, exc.value.orm_col) == (1, 6)

    def test_lexer_and_parser_columns_agree(self, plain_adapter):
        with pytest.raises(OrmSyntaxError) as parse_error:
            parse_with("x = = 1\n", plain_adapter)
        with pytest.raises(OrmLexError) as lex_error:
            parse_with("x = $ 1\n", plain_adapter)
        assert parse_error.value.orm_col == lex_error.value.orm_col == 5

    def test_uppercase_u_prefix_has_no_kind(self, plain_adapter):
        for source, kind in [("U'a'", None), ("u'a'", "u"), ("U'a' u'b'", None)]:
            tree = parse_with(f"x = {source}\n", plain_adapter)
            assert tree.body[0].value.kind == kind, source
        assert_same_as_python("x = U'abc'\n", plain_adapter)
