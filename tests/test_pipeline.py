"""End-to-end tests: Afan Oromo source in, working Python out."""

from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path

import pytest

from oromscript import execute, grapheme_len, split_graphemes, transpile
from oromscript.adapter import Adapter, AdapterRegistry
from oromscript.errors import OrmLexError, OrmSyntaxError

ROOT = Path(__file__).parent.parent


def reference_transpile(source: str, adapter: Adapter) -> str:
    """The earlier route: Python's tokenizer, then ``ast.parse``.

    Used to check that the hand-written lexer and parser give the same result.
    """
    mapping = {v: k for k, v in {**adapter.keyword_map, **adapter.builtin_map}.items()}
    tokens = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.NAME and tok.string in mapping:
            tok = tok._replace(string=mapping[tok.string])
        tokens.append(tok)
    return ast.unparse(ast.parse(tokenize.untokenize(tokens)))


PROGRAMS = [
    'agarsiisi("Akkam, Addunyaa!")\n',
    "x = 5\nyoo x > 3:\n    agarsiisi('guddaa')\nyoo_miti:\n    agarsiisi('xiqqaa')\n",
    "hanga i keessa lakkoofsa(3):\n    agarsiisi(i)\n",
    "hojii ida(a, b=2, *c, **d):\n    deebi a + b\n",
    "hojii f(n):\n    yoo n < 2:\n        deebi n\n    deebi f(n - 1) + f(n - 2)\n",
    "gosa Barataa:\n    hojii __init__(of, maqaa):\n        of.maqaa = maqaa\n",
    "gosa A(B, metaclass=M):\n    x: lakki = 3\n",
    "yeroo x < 10:\n    x += 1\n    yoo x == 5:\n        addaan_kut\n    itti_fufuu\n",
    "yaali:\n    x = 1 / 0\ndogoggora ZeroDivisionError akka e:\n    agarsiisi(e)\ndhuma:\n    agarsiisi('xumure')\n",
    "waliin bani('f') akka f:\n    darbii\n",
    "x = [i * 2 hanga i keessa lakkoofsa(5) yoo i != 3]\n",
    "x = {k: v hanga k, v keessa galmee(a=1).items()}\n",
    "f = hojii_gabaabaa x, y=2: x + y\n",
    "a = dhugaa fi sobaa yookaan_immoo Wanti_hin_jirre\n",
    "x = 1 yoo a yoo_miti 2\n",
    "fidi os\nirra os.path fidi join akka j\n",
    "haqi x[0], y\nmirkaanessi x, 'msg'\nol_kaasi ValueError('x')\n",
    "hojii g():\n    kennii 1\n    kennii_irra h()\n",
    "hojii h():\n    addunyaa z\n    z = 1\n",
    "x = tarree(lakkoofsa(3))\ny = dheerina(x) + walitti_qabama(x).__len__()\n",
    "walsimsiisi x:\n    haala 1:\n        deebi 'a'\n    haala [a, b]:\n        deebi a\n    haala {'k': v}:\n        deebi v\n    haala _:\n        deebi 'z'\n",
    "x = 'yoo' + \"hanga\"\n",
    "x = '''yoo\nhanga'''\n",
    "# yoo hanga\nx = 1  # deebi\n",
    "yoo a:\n    yoo b:\n        c\n    yoo_miti:\n        d\n",
    "x = (1 +\n     2)\n",
    "x = 1 + \\\n    2\n",
    "x = 0x1F + 0b11 + 1_000 + 2.5e3 + 3j\n",
    "x = a[1:2, ::3]\n",
    "gosa K:\n    @staticmethod\n    hojii m():\n        darbii\n",
    "hojii_async = 1\n",
    "x = yoo_miti_name\n",
]


@pytest.mark.parametrize("source", PROGRAMS, ids=[repr(p)[:50] for p in PROGRAMS])
def test_matches_reference_route(source, oromo_adapter):
    assert transpile(source) == reference_transpile(source, oromo_adapter)


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.orm")), ids=str)
def test_examples_match_reference_route(path, oromo_adapter):
    source = path.read_text(encoding="utf-8")
    if "f'" in source or 'f"' in source:
        pytest.skip("reference route cannot translate names inside f-strings")
    assert transpile(source) == reference_transpile(source, oromo_adapter)


@pytest.mark.parametrize("path", sorted((ROOT / "examples").glob("*.orm")), ids=str)
def test_examples_produce_valid_python(path):
    result = transpile(path.read_text(encoding="utf-8"))
    ast.parse(result)
    compile(result, str(path), "exec")


class TestRunning:
    def test_hello_world(self, capsys):
        execute('agarsiisi("Akkam, Addunyaa!")')
        assert capsys.readouterr().out == "Akkam, Addunyaa!\n"

    def test_fibonacci(self, capsys):
        execute(
            "hojii fib(n):\n"
            "    yoo n < 2:\n"
            "        deebi n\n"
            "    deebi fib(n - 1) + fib(n - 2)\n"
            "agarsiisi(fib(10))\n"
        )
        assert capsys.readouterr().out == "55\n"

    def test_class_and_f_string(self, capsys):
        execute(
            "gosa Barataa:\n"
            "    hojii __init__(of, maqaa, umri):\n"
            "        of.maqaa = maqaa\n"
            "        of.umri = umri\n"
            "    hojii of_ibsi(of):\n"
            "        agarsiisi(f'{of.maqaa}: {of.umri}')\n"
            "Barataa('Chaltu', 20).of_ibsi()\n"
        )
        assert capsys.readouterr().out == "Chaltu: 20\n"

    def test_f_string_uses_oromo_builtins(self, capsys):
        execute("x = tarree(lakkoofsa(3))\nagarsiisi(f'{dheerina(x)} {x!r}')\n")
        assert capsys.readouterr().out == "3 [0, 1, 2]\n"

    def test_hudhaa_builtin(self, capsys):
        execute("agarsiisi(walitti_ida'i([1, 2, 3]))\n")
        assert capsys.readouterr().out == "6\n"

    def test_hudhaa_builtin_typed_with_curly_apostrophe(self, capsys):
        execute("agarsiisi(walitti_ida\u2019i([1, 2, 3]))\n")
        assert capsys.readouterr().out == "6\n"

    def test_hudhaa_builtin_inside_f_string(self, capsys):
        execute("agarsiisi(f'{walitti_ida\u2019i([4, 5])}')\n")
        assert capsys.readouterr().out == "9\n"

    def test_loops_and_conditions(self, capsys):
        execute(
            "hanga i keessa lakkoofsa(5):\n"
            "    yoo i == 1:\n"
            "        itti_fufuu\n"
            "    yookaan i == 4:\n"
            "        addaan_kut\n"
            "    yoo_miti:\n"
            "        agarsiisi(i)\n"
        )
        assert capsys.readouterr().out == "0\n2\n3\n"

    def test_exceptions(self, capsys):
        execute(
            "yaali:\n"
            "    x = 1 / 0\n"
            "dogoggora ZeroDivisionError:\n"
            "    agarsiisi('error')\n"
            "dhuma:\n"
            "    agarsiisi('done')\n"
        )
        assert capsys.readouterr().out == "error\ndone\n"

    def test_comprehension_and_lambda(self, capsys):
        execute(
            "f = hojii_gabaabaa x: x * 2\n"
            "agarsiisi(tarree(jijjiiri(f, [i hanga i keessa lakkoofsa(3)])))\n"
        )
        assert capsys.readouterr().out == "[0, 2, 4]\n"

    def test_generator(self, capsys):
        execute("hojii g():\n    kennii 1\n    kennii 2\n" "agarsiisi(tarree(g()))\n")
        assert capsys.readouterr().out == "[1, 2]\n"

    def test_match_statement(self, capsys):
        execute(
            "hojii d(n):\n"
            "    walsimsiisi n:\n"
            "        haala 1:\n"
            "            deebi 'tokko'\n"
            "        haala [a, b]:\n"
            "            deebi a + b\n"
            "        haala _:\n"
            "            deebi 'kan biraa'\n"
            "agarsiisi(d(1), d([1, 2]), d(9))\n"
        )
        assert capsys.readouterr().out == "tokko 3 kan biraa\n"

    def test_global_variable(self, capsys):
        execute("z = 1\nhojii h():\n    addunyaa z\n    z = 2\nh()\nagarsiisi(z)\n")
        assert capsys.readouterr().out == "2\n"

    def test_runtime_error_is_a_normal_python_error(self):
        with pytest.raises(ZeroDivisionError):
            execute("x = 1 / 0\n")

    def test_execute_uses_given_globals(self):
        scope: dict[str, object] = {}
        execute("x = 41 + 1\n", globals=scope)
        assert scope["x"] == 42


class TestErrors:
    def test_lex_error_through_transpile(self):
        with pytest.raises(OrmLexError) as exc:
            transpile("x = 1\ny = $\n")
        assert (exc.value.code, exc.value.orm_line) == ("E0001", 2)

    def test_syntax_error_through_transpile(self):
        with pytest.raises(OrmSyntaxError) as exc:
            transpile("yoo :\n")
        assert exc.value.code == "E0010"

    def test_unterminated_string_through_transpile(self):
        with pytest.raises(OrmLexError):
            transpile('agarsiisi("')

    def test_error_line_is_in_original_source(self):
        with pytest.raises(OrmSyntaxError) as exc:
            transpile("x = 1\n\n\nhojii f(:\n    darbii\n)\n")
        assert exc.value.orm_line == 4

    def test_unclosed_bracket_points_at_the_bracket(self):
        with pytest.raises(OrmLexError) as exc:
            transpile("x = 1\n\n\nhojii f(:\n    darbii\n")
        assert exc.value.orm_line == 4

    def test_deeply_nested_brackets_raise_an_orm_error(self):
        with pytest.raises(OrmSyntaxError):
            transpile("x = " + "(" * 5000 + "1" + ")" * 5000 + "\n")

    def test_very_long_operator_chain_raises_an_orm_error_or_works(self):
        source = "x = " + " + ".join(["a"] * 20000) + "\n"
        try:
            transpile(source)
        except OrmSyntaxError as exc:
            assert "nested too deeply" in exc.message

    def test_error_at_end_of_file_names_a_real_line(self):
        with pytest.raises(OrmSyntaxError) as exc:
            transpile("hojii f():\n")
        assert exc.value.orm_line == 1

    def test_unknown_language(self):
        from oromscript.errors import OrmAdapterError

        with pytest.raises(OrmAdapterError):
            transpile("x = 1", lang="klingon")

    def test_strict_mode_still_works(self):
        from oromscript.errors import OrmNameError

        with pytest.raises(OrmNameError):
            transpile("agarsiisi(undefined_name)\n", strict=True)

    def test_source_map_is_still_returned(self):
        py_source, map_json = transpile("x = 1\n", emit_map=True)
        assert py_source == "x = 1"
        assert '"version"' in map_json


class TestOtherLanguages:
    def test_a_second_adapter_works_with_the_same_engine(self):
        adapter = Adapter(
            lang="german",
            keyword_map={"if": "wenn", "else": "sonst", "print": "drucke"},
            builtin_map={},
            error_messages={},
        )
        AdapterRegistry._adapters["german"] = adapter
        try:
            result = transpile(
                "wenn x:\n    drucke(1)\nsonst:\n    drucke(2)\n", lang="german"
            )
        finally:
            del AdapterRegistry._adapters["german"]
        assert result == "if x:\n    print(1)\nelse:\n    print(2)"


class TestGraphemeExports:
    def test_exported_from_package(self):
        assert split_graphemes("chaa") == ["ch", "aa"]
        assert grapheme_len("chaa") == 2


@pytest.mark.skipif(sys.version_info < (3, 12), reason="needs Python 3.12 f-strings")
def test_nested_same_quote_f_string(capsys):
    execute("x = 2\nagarsiisi(f'{f'{x}'}')\n")
    assert capsys.readouterr().out == "2\n"
