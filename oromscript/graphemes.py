"""
oromscript.graphemes
~~~~~~~~~~~~~~~~~~~~
Grapheme helpers for Afan Oromo (Qubee) text.

A grapheme here is one written unit of the language. Some units use more
than one character:

* digraphs: ``ch``, ``dh``, ``ny``, ``ph``, ``sh`` (and ``ts``, ``zy``)
* long vowels: ``aa``, ``ee``, ``ii``, ``oo``, ``uu``
* doubled consonants: ``bb``, ``kk``, and doubled digraphs such as ``cch``
* the hudhaa (apostrophe) that marks a glottal stop, as in ``ba'e``. It counts
  as a letter of its own.

A unit is written in one case (``aa``, ``AA``) or capitalised (``Aa``, ``Ch``).
A mix such as ``aA`` is two units.

The lexer uses :func:`normalize_hudhaa` so that a keyword typed with a curly
apostrophe still matches the keyword map. The other helpers are public tools
for editors and error messages that need to count or cut words by letter.
"""

from __future__ import annotations

import ast
import functools
import re
import unicodedata
from collections.abc import Iterator

#: Characters that people type for the hudhaa. Only the first is canonical.
HUDHAA = "'"
HUDHAA_VARIANTS = "'’ʼ‘"

_HUDHAA_TABLE = {ord(ch): HUDHAA for ch in HUDHAA_VARIANTS}

_DIGRAPHS = ("ch", "dh", "ny", "ph", "sh", "ts", "zy")
_VOWELS = "aeiou"
_CONSONANTS = "bcdfghjklmnpqrstvwxyz"


def _digraph_spellings(digraph: str) -> list[str]:
    """Every mix of upper and lower case for a digraph: ``ch``, ``Ch``, ``cH``..."""
    first, second = digraph[0], digraph[1]
    return [a + b for a in (first, first.upper()) for b in (second, second.upper())]


def _doubled_digraph_spellings(digraph: str) -> list[str]:
    """``cch``, ``CCH`` and ``Cch`` for the digraph ``ch``."""
    first, rest = digraph[0], digraph[1:]
    return [first * 2 + rest, first.upper() * 2 + rest.upper(), first.upper() + digraph]


def _doubles(letters: str, *, capitalised: bool) -> list[str]:
    """``aa`` and ``AA`` for each letter, and ``Aa`` if ``capitalised``.

    A mix such as ``aA`` is never a unit.
    """
    spellings = []
    for letter in letters:
        spellings += [letter * 2, letter.upper() * 2]
        if capitalised:
            spellings.append(letter.upper() + letter)
    return spellings


# Longest alternatives first so "cch" wins over "c" + "ch". A long vowel may be
# capitalised ("Aanaa"); a doubled consonant is not (no word starts with "Bb").
_GRAPHEME_RE = re.compile(
    "|".join(
        (
            "(?P<geminate_digraph>"
            + "|".join(
                re.escape(w) for d in _DIGRAPHS for w in _doubled_digraph_spellings(d)
            )
            + ")",
            "(?P<digraph>"
            + "|".join(re.escape(w) for d in _DIGRAPHS for w in _digraph_spellings(d))
            + ")",
            "(?P<long_vowel>"
            + "|".join(re.escape(w) for w in _doubles(_VOWELS, capitalised=True))
            + ")",
            "(?P<geminate>"
            + "|".join(re.escape(w) for w in _doubles(_CONSONANTS, capitalised=False))
            + ")",
            r"(?P<other>.)",
        )
    ),
    re.DOTALL,
)

#: Kinds of grapheme that are written with more than one character.
MULTI_CHARACTER_KINDS = frozenset(
    {"geminate_digraph", "digraph", "long_vowel", "geminate"}
)


class Grapheme(ast.AST):
    """A tree node for one written unit of an Afan Oromo word.

    ``text`` is the unit (``dh``, ``aa``, ``bb``, ``'``...). ``kind`` is one of
    ``geminate_digraph``, ``digraph``, ``long_vowel``, ``geminate``, ``hudhaa``,
    ``letter`` or ``other``. ``start`` and ``end`` are character offsets in the
    word (``end`` is exclusive).

    The parser attaches a tuple of these nodes to every name in the tree as the
    attribute ``graphemes``. The attribute is not one of the node's ``_fields``,
    so ``ast.walk``, ``ast.dump``, ``ast.unparse`` and ``compile`` ignore it.
    Use :func:`iter_graphemes` to find them.
    """

    _fields = ("text", "kind", "start", "end")
    text: str
    kind: str
    start: int
    end: int

    def __init__(
        self, text: str = "", kind: str = "other", start: int = 0, end: int = 0
    ) -> None:
        self.text = text
        self.kind = kind
        self.start = start
        self.end = end

    @property
    def is_multi_character(self) -> bool:
        """True for digraphs, long vowels and doubled consonants."""
        return self.kind in MULTI_CHARACTER_KINDS


def normalize_hudhaa(text: str) -> str:
    """Return ``text`` with every hudhaa variant replaced by ``'``."""
    return text.translate(_HUDHAA_TABLE)


@functools.lru_cache(maxsize=4096)
def grapheme_nodes(word: str) -> tuple[Grapheme, ...]:
    """Return the :class:`Grapheme` nodes of ``word``.

    A combining mark stays attached to the unit before it. The result is
    cached, so every use of the same name shares the same nodes. Do not
    change them.

    >>> [g.text for g in grapheme_nodes("dhaabbata")]
    ['dh', 'aa', 'bb', 'a', 't', 'a']
    """
    nodes: list[Grapheme] = []
    for match in _GRAPHEME_RE.finditer(word):
        piece = match.group(0)
        kind = match.lastgroup or "other"
        if kind == "other":
            if piece in HUDHAA_VARIANTS:
                kind = "hudhaa"
            elif piece.isalpha():
                kind = "letter"
        if nodes and unicodedata.combining(piece[0]):
            last = nodes[-1]
            nodes[-1] = Grapheme(
                text=last.text + piece,
                kind=last.kind,
                start=last.start,
                end=match.end(),
            )
        else:
            nodes.append(
                Grapheme(text=piece, kind=kind, start=match.start(), end=match.end())
            )
    return tuple(nodes)


def split_graphemes(word: str) -> list[str]:
    """Split ``word`` into Afan Oromo graphemes.

    A combining mark stays attached to the unit before it.

    >>> split_graphemes("dhaabbata")
    ['dh', 'aa', 'bb', 'a', 't', 'a']
    """
    return [node.text for node in grapheme_nodes(word)]


def grapheme_len(word: str) -> int:
    """Return how many graphemes ``word`` has."""
    return len(grapheme_nodes(word))


#: Node types whose name the parser breaks into graphemes, and the field it uses.
_NAME_FIELDS: dict[type[ast.AST], str] = {
    ast.Name: "id",
    ast.Attribute: "attr",
    ast.arg: "arg",
    ast.keyword: "arg",
    ast.FunctionDef: "name",
    ast.AsyncFunctionDef: "name",
    ast.ClassDef: "name",
    ast.ExceptHandler: "name",
    ast.alias: "name",
}


def iter_graphemes(tree: ast.AST) -> Iterator[tuple[ast.AST, tuple[Grapheme, ...]]]:
    """Yield ``(node, graphemes)`` for every named node in ``tree``.

    Works on any tree. If the parser did not attach graphemes, they are made now.
    """
    for node in ast.walk(tree):
        field = _NAME_FIELDS.get(type(node))
        if field is None:
            continue
        name = getattr(node, field, None)
        if not name:
            continue
        found = getattr(node, "graphemes", None)
        yield node, found if found is not None else grapheme_nodes(name)
