from __future__ import annotations

import pytest

from oromscript.graphemes import (
    HUDHAA,
    HUDHAA_VARIANTS,
    grapheme_len,
    normalize_hudhaa,
    split_graphemes,
)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("", []),
        ("a", ["a"]),
        ("ba", ["b", "a"]),
        # digraphs
        ("chaltu", ["ch", "a", "l", "t", "u"]),
        ("dhufe", ["dh", "u", "f", "e"]),
        ("nyaata", ["ny", "aa", "t", "a"]),
        ("phaaphaa", ["ph", "aa", "ph", "aa"]),
        ("shan", ["sh", "a", "n"]),
        # long vowels
        ("aa", ["aa"]),
        ("ee", ["ee"]),
        ("ii", ["ii"]),
        ("oo", ["oo"]),
        ("uu", ["uu"]),
        ("laaffisa", ["l", "aa", "ff", "i", "s", "a"]),
        # doubled consonants
        ("bb", ["bb"]),
        ("kk", ["kk"]),
        ("dhaabbata", ["dh", "aa", "bb", "a", "t", "a"]),
        # doubled digraphs
        ("cchaa", ["cch", "aa"]),
        ("ddhaa", ["ddh", "aa"]),
        ("ppha", ["pph", "a"]),
        ("ssha", ["ssh", "a"]),
        # a vowel written three times is one long vowel plus one more
        ("aaa", ["aa", "a"]),
        # letters that are not Afan Oromo stay single
        ("xyz", ["x", "y", "z"]),
        ("123", ["1", "2", "3"]),
    ],
)
def test_split_graphemes(word: str, expected: list[str]) -> None:
    assert split_graphemes(word) == expected


@pytest.mark.parametrize("word", ["Chaltu", "CHALTU", "cHaLtU", "ChAaLtU"])
def test_digraphs_are_found_in_any_case(word: str) -> None:
    pieces = split_graphemes(word)
    assert pieces[0].lower() == "ch"
    assert "".join(pieces) == word


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("AA", ["AA"]),
        ("Aa", ["Aa"]),
        ("Aanaa", ["Aa", "n", "aa"]),
        ("Eenyu", ["Ee", "ny", "u"]),
        ("BB", ["BB"]),
        ("Cchaa", ["Cch", "aa"]),
        ("CCHAA", ["CCH", "AA"]),
        ("SSH", ["SSH"]),
    ],
)
def test_units_may_be_upper_case_or_capitalised(word, expected) -> None:
    assert split_graphemes(word) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("aA", ["a", "A"]),
        ("eE", ["e", "E"]),
        ("bB", ["b", "B"]),
        ("Bb", ["B", "b"]),
        ("kK", ["k", "K"]),
        ("cCh", ["c", "Ch"]),
        ("ccH", ["cc", "H"]),
    ],
)
def test_a_mix_of_cases_is_not_one_unit(word, expected) -> None:
    assert split_graphemes(word) == expected


def test_pieces_always_rebuild_the_word() -> None:
    for word in ["dhaabbata", "ba'e", "Nyaata", "qabsoo", "hojii_gabaabaa", "x-y z"]:
        assert "".join(split_graphemes(word)) == word


def test_hudhaa_is_one_grapheme() -> None:
    assert split_graphemes("ba'e") == ["b", "a", "'", "e"]
    assert grapheme_len("ba'e") == 4


@pytest.mark.parametrize("mark", list(HUDHAA_VARIANTS))
def test_every_hudhaa_variant_is_a_single_grapheme(mark: str) -> None:
    assert split_graphemes(f"ba{mark}e") == ["b", "a", mark, "e"]


def test_combining_mark_stays_with_previous_letter() -> None:
    word = "é"  # e + combining acute accent
    assert split_graphemes(word) == [word]
    assert grapheme_len(word) == 1


def test_combining_mark_after_digraph() -> None:
    word = "ch́a"
    assert split_graphemes(word) == ["ch́", "a"]


def test_combining_mark_at_start_is_kept() -> None:
    assert split_graphemes("́a") == ["́", "a"]


def test_grapheme_len_counts_units_not_characters() -> None:
    assert len("dhaabbata") == 9
    assert grapheme_len("dhaabbata") == 6
    assert grapheme_len("") == 0


def test_newline_is_a_grapheme() -> None:
    assert split_graphemes("a\nb") == ["a", "\n", "b"]


def test_non_latin_text_is_split_per_character() -> None:
    assert split_graphemes("ሰላም") == ["ሰ", "ላ", "ም"]


@pytest.mark.parametrize("mark", list(HUDHAA_VARIANTS))
def test_normalize_hudhaa_variants(mark: str) -> None:
    assert normalize_hudhaa(f"ba{mark}e") == "ba'e"


def test_normalize_hudhaa_leaves_other_text_alone() -> None:
    assert normalize_hudhaa("hojii") == "hojii"
    assert normalize_hudhaa("") == ""
    assert normalize_hudhaa('say "hi"') == 'say "hi"'


def test_normalize_hudhaa_changes_every_occurrence() -> None:
    assert normalize_hudhaa("a’bʼc‘d") == "a'b'c'd"


def test_canonical_hudhaa_is_ascii_apostrophe() -> None:
    assert HUDHAA == "'"
    assert HUDHAA in HUDHAA_VARIANTS


# ── Grapheme nodes ───────────────────────────────────────────────────────────
import ast  # noqa: E402
import copy  # noqa: E402
import pickle  # noqa: E402

from oromscript.graphemes import (  # noqa: E402
    MULTI_CHARACTER_KINDS,
    Grapheme,
    grapheme_nodes,
    iter_graphemes,
)
from oromscript.lexer import OrmLexer  # noqa: E402
from oromscript.parser import OrmParser  # noqa: E402


def parse(source, adapter):
    return OrmParser(adapter).parse(OrmLexer(source, adapter).tokenize())


class TestNodes:
    def test_node_is_an_ast_node(self):
        node = grapheme_nodes("dh")[0]
        assert isinstance(node, ast.AST)
        assert isinstance(node, Grapheme)
        assert node._fields == ("text", "kind", "start", "end")

    @pytest.mark.parametrize(
        ("word", "expected"),
        [
            ("dhaabbata", [
                ("dh", "digraph", 0, 2),
                ("aa", "long_vowel", 2, 4),
                ("bb", "geminate", 4, 6),
                ("a", "letter", 6, 7),
                ("t", "letter", 7, 8),
                ("a", "letter", 8, 9),
            ]),
            ("cchaa", [("cch", "geminate_digraph", 0, 3), ("aa", "long_vowel", 3, 5)]),
            ("ba'e", [
                ("b", "letter", 0, 1),
                ("a", "letter", 1, 2),
                ("'", "hudhaa", 2, 3),
                ("e", "letter", 3, 4),
            ]),
            ("Aanaa", [("Aa", "long_vowel", 0, 2), ("n", "letter", 2, 3),
                       ("aa", "long_vowel", 3, 5)]),
            ("x1_", [("x", "letter", 0, 1), ("1", "other", 1, 2), ("_", "other", 2, 3)]),
            ("", []),
        ],
    )  # fmt: skip
    def test_text_kind_and_offsets(self, word, expected):
        got = [(g.text, g.kind, g.start, g.end) for g in grapheme_nodes(word)]
        assert got == expected

    @pytest.mark.parametrize("mark", list(HUDHAA_VARIANTS))
    def test_every_hudhaa_variant_has_kind_hudhaa(self, mark):
        assert grapheme_nodes(f"a{mark}")[1].kind == "hudhaa"

    def test_multi_character_property(self):
        flags = {g.text: g.is_multi_character for g in grapheme_nodes("dhaabbata")}
        assert flags == {"dh": True, "aa": True, "bb": True, "a": False, "t": False}

    def test_multi_character_kinds_constant(self):
        assert {
            "geminate_digraph",
            "digraph",
            "long_vowel",
            "geminate",
        } == MULTI_CHARACTER_KINDS

    def test_offsets_cover_the_word(self):
        word = "dhaabbata'e"
        nodes = grapheme_nodes(word)
        assert nodes[0].start == 0 and nodes[-1].end == len(word)
        assert all(a.end == b.start for a, b in zip(nodes, nodes[1:], strict=False))
        assert "".join(g.text for g in nodes) == word

    def test_combining_mark_joins_the_previous_node(self):
        nodes = grapheme_nodes("ch́a")
        assert [g.text for g in nodes] == ["ch́", "a"]
        assert nodes[0].kind == "digraph"
        assert (nodes[0].start, nodes[0].end) == (0, 3)

    def test_results_are_cached_and_shared(self):
        assert grapheme_nodes("maqaa") is grapheme_nodes("maqaa")

    def test_result_is_a_tuple(self):
        assert isinstance(grapheme_nodes("maqaa"), tuple)

    def test_split_graphemes_uses_the_nodes(self):
        assert split_graphemes("maqaa") == [g.text for g in grapheme_nodes("maqaa")]

    def test_dump_and_unparse_style_helpers_work(self):
        node = grapheme_nodes("dh")[0]
        assert ast.dump(node) == "Grapheme(text='dh', kind='digraph', start=0, end=2)"

    def test_nodes_can_be_copied_and_pickled(self):
        node = grapheme_nodes("dhaa")[0]
        assert copy.deepcopy(node).text == "dh"
        assert pickle.loads(pickle.dumps(node)).kind == "digraph"  # noqa: S301

    def test_node_can_be_built_by_hand(self):
        node = Grapheme("aa", "long_vowel", 0, 2)
        assert (node.text, node.kind, node.start, node.end) == (
            "aa",
            "long_vowel",
            0,
            2,
        )
        assert Grapheme().kind == "other"


class TestOnTrees:
    SOURCE = (
        "gosa Barataa:\n"
        "    hojii __init__(of, maqaa, dhaabbata=1):\n"
        "        of.maqaa = maqaa\n"
        "        yaali:\n"
        "            agarsiisi(xiyyeeffannoo=maqaa)\n"
        "        dogoggora Dogoggora akka dogoggoraa:\n"
        "            darbii\n"
        "fidi lakkoofsa akka lakkoofsaa\n"
    )

    def collect(self, adapter):
        tree = parse(self.SOURCE, adapter)
        return {
            (type(node).__name__, "".join(g.text for g in grams)): grams
            for node, grams in iter_graphemes(tree)
        }

    def test_every_named_node_type_has_graphemes(self, oromo_adapter):
        got = self.collect(oromo_adapter)
        kinds = {kind for kind, _ in got}
        assert kinds >= {
            "ClassDef", "FunctionDef", "arg", "Name", "Attribute", "keyword",
            "ExceptHandler", "alias",
        }  # fmt: skip

    def test_class_name(self, oromo_adapter):
        grams = self.collect(oromo_adapter)[("ClassDef", "Barataa")]
        assert [g.text for g in grams] == ["B", "a", "r", "a", "t", "aa"]

    def test_parameter_names(self, oromo_adapter):
        got = self.collect(oromo_adapter)
        assert [g.text for g in got[("arg", "dhaabbata")]][:3] == ["dh", "aa", "bb"]
        assert [g.text for g in got[("arg", "maqaa")]][-1] == "aa"

    def test_attribute_and_name(self, oromo_adapter):
        got = self.collect(oromo_adapter)
        assert ("Attribute", "maqaa") in got and ("Name", "maqaa") in got

    def test_keyword_argument_name(self, oromo_adapter):
        grams = self.collect(oromo_adapter)[("keyword", "xiyyeeffannoo")]
        assert [g.text for g in grams if g.is_multi_character] == [
            "yy",
            "ee",
            "ff",
            "nn",
            "oo",
        ]

    def test_exception_name_and_import_alias(self, oromo_adapter):
        got = self.collect(oromo_adapter)
        assert ("ExceptHandler", "dogoggoraa") in got
        # An alias describes the imported name; "lakkoofsa" is translated to "range".
        assert ("alias", "range") in got

    def test_parser_attaches_the_attribute(self, oromo_adapter):
        tree = parse("maqaa = dhaabbata\n", oromo_adapter)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert isinstance(node.graphemes, tuple)
                assert all(isinstance(g, Grapheme) for g in node.graphemes)

    def test_attached_nodes_are_the_cached_ones(self, oromo_adapter):
        tree = parse("maqaa = 1\nmaqaa\n", oromo_adapter)
        names = [n for n in ast.walk(tree) if isinstance(n, ast.Name)]
        assert names[0].graphemes is names[1].graphemes is grapheme_nodes("maqaa")

    def test_ast_walk_does_not_visit_graphemes(self, oromo_adapter):
        tree = parse("maqaa = dhaabbata\n", oromo_adapter)
        assert not any(isinstance(n, Grapheme) for n in ast.walk(tree))

    def test_dump_is_the_same_as_for_python_parse(self, oromo_adapter):
        tree = parse("maqaa = dhaabbata(1)\n", oromo_adapter)
        assert ast.dump(tree) == ast.dump(ast.parse("maqaa = dhaabbata(1)\n"))

    def test_tree_still_compiles_and_runs(self, oromo_adapter):
        tree = parse("maqaa = 40 + 2\n", oromo_adapter)
        namespace: dict[str, object] = {}
        exec(compile(tree, "<t>", "exec"), namespace)  # noqa: S102
        assert namespace["maqaa"] == 42

    def test_tree_can_be_copied(self, oromo_adapter):
        tree = parse("maqaa = dhaabbata\n", oromo_adapter)
        copied = copy.deepcopy(tree)
        names = [n for n in ast.walk(copied) if isinstance(n, ast.Name)]
        assert names[0].graphemes[0].text == "m"

    def test_f_string_field_names_have_graphemes(self, oromo_adapter):
        tree = parse("x = f'{maqaa.dhaabbata}'\n", oromo_adapter)
        found = {"".join(g.text for g in grams) for _, grams in iter_graphemes(tree)}
        assert {"maqaa", "dhaabbata"} <= found

    def test_names_translated_from_keywords_show_python_names(self, oromo_adapter):
        tree = parse("agarsiisi(1)\n", oromo_adapter)
        names = ["".join(g.text for g in grams) for _, grams in iter_graphemes(tree)]
        assert names == ["print"]

    def test_iter_graphemes_on_a_tree_without_the_attribute(self):
        tree = ast.parse("dhaabbata = 1\ndef maqaa(): pass\n")
        got = {
            type(n).__name__: [g.text for g in grams]
            for n, grams in iter_graphemes(tree)
        }
        assert got["Name"][:3] == ["dh", "aa", "bb"]
        assert got["FunctionDef"][-1] == "aa"

    def test_iter_graphemes_skips_unnamed_nodes(self):
        tree = ast.parse(
            "f(*a, **k)\nimport x\nraise\ntry:\n    pass\nexcept:\n    pass\n"
        )
        names = [type(n).__name__ for n, _ in iter_graphemes(tree)]
        assert "ExceptHandler" not in names  # a bare except has no name
        assert "keyword" not in names  # **k has no keyword name
