"""
oromscript.lexer
~~~~~~~~~~~~~~~~
A hand-written lexer for Afan Oromo (or any localised) Python source.

It reads the source in one pass with a single compiled regular expression,
tracks indentation itself, and replaces local-language names with their
Python equivalents. It produces standard ``tokenize.TokenInfo`` objects, so
other tools can read its output.

This is the first stage of the OromScript transpile pipeline.
"""

from __future__ import annotations

import functools
import re
import tokenize as py_tokenize
import unicodedata
from typing import TYPE_CHECKING, NoReturn

from ._gc import gc_paused
from .errors import OrmLexError
from .graphemes import HUDHAA, HUDHAA_VARIANTS, normalize_hudhaa

if TYPE_CHECKING:
    from .adapter import Adapter

NAME = py_tokenize.NAME
NUMBER = py_tokenize.NUMBER
STRING = py_tokenize.STRING
OP = py_tokenize.OP
NEWLINE = py_tokenize.NEWLINE
NL = py_tokenize.NL
COMMENT = py_tokenize.COMMENT
INDENT = py_tokenize.INDENT
DEDENT = py_tokenize.DEDENT
ENDMARKER = py_tokenize.ENDMARKER

_TAB_SIZE = 8
CONTINUATION_EOF = "Unexpected end of file after line continuation"
_OPENERS = frozenset("([{")
_CLOSERS = frozenset(")]}")
_STRING_PREFIXES = frozenset({"r", "b", "f", "u", "rb", "br", "fr", "rf"})

# ── Regular expression pieces ────────────────────────────────────────────────

_DIGITS = r"\d(?:_?\d)*"
_EXPONENT = rf"[eE][+-]?{_DIGITS}"
_POINT_FLOAT = rf"(?:{_DIGITS}\.(?:{_DIGITS})?|\.{_DIGITS})(?:{_EXPONENT})?"
_EXP_FLOAT = rf"{_DIGITS}{_EXPONENT}"
_NUMBER = "|".join(
    (
        r"0[xX](?:_?[0-9a-fA-F])+",
        r"0[bB](?:_?[01])+",
        r"0[oO](?:_?[0-7])+",
        rf"(?:{_POINT_FLOAT}|{_EXP_FLOAT}|{_DIGITS})[jJ]",
        _POINT_FLOAT,
        _EXP_FLOAT,
        _DIGITS,
    )
)

_PREFIX = r"(?:[rR][bBfF]?|[bB][rR]?|[fF][rR]?|[uU])?"
_STRING = "|".join(
    (
        rf"{_PREFIX}'''[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''",
        rf'{_PREFIX}"""[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""',
        # A short string may not start with three quotes: an unterminated triple
        # quote is an error, not an empty string followed by another string.
        rf"{_PREFIX}'(?!'')[^'\\\n]*(?:\\.[^'\\\n]*)*'",
        rf'{_PREFIX}"(?!"")[^"\\\n]*(?:\\.[^"\\\n]*)*"',
    )
)

_OPERATORS = (
    r"\*\*=|//=|>>=|<<=|\.\.\.|->|:=|!=|==|<=|>=|\*\*|//|>>|<<"
    r"|\+=|-=|\*=|/=|%=|&=|\|=|\^=|@=|[-+*/%&|^~<>()\[\]{},:.;=@]"
)

# A name starts with a letter or underscore. Later characters may be anything that
# is not ASCII, so that combining marks work; ``str.isidentifier`` checks them.
_NAME = r"[^\W\d](?:\w|[^\x00-\x7f])*"
_F_PREFIXES = frozenset({"f", "fr", "rf"})

_HUDHAA_CLASS = "[" + re.escape(HUDHAA_VARIANTS) + "]"


@functools.lru_cache(maxsize=32)
def _build_scanner(apostrophe_words: tuple[str, ...]) -> re.Pattern[str]:
    """Compile the master token pattern.

    Keywords that contain a hudhaa (for example ``walitti_ida'i``) cannot be
    matched by the plain name rule, so they get their own first alternative.
    """
    parts = [
        r"(?P<ws>[ \t\f]+)",
        r"(?P<comment>#[^\n]*)",
        r"(?P<newline>\n)",
        r"(?P<cont>\\\n)",
        rf"(?P<string>{_STRING})",
        rf"(?P<number>{_NUMBER})",
    ]
    if apostrophe_words:
        words = sorted(apostrophe_words, key=len, reverse=True)
        alternatives = "|".join(
            re.escape(word).replace(re.escape(HUDHAA), _HUDHAA_CLASS) for word in words
        )
        parts.append(rf"(?P<hudhaa>(?:{alternatives})(?![\w]))")
    parts.append(rf"(?P<name>{_NAME})")
    parts.append(rf"(?P<op>{_OPERATORS})")
    return re.compile("|".join(parts), re.DOTALL)


def _first_invalid_character(name: str) -> int:
    """Return the index of the first character that cannot be in a name."""
    for index, char in enumerate(name):
        if not (char if index == 0 else "_" + char).isidentifier():
            return index
    return 0


def _is_fstring(text: str) -> bool:
    prefix = text[: text.find(text[-1])]
    return "f" in prefix or "F" in prefix


class OrmLexer:
    """Tokenise a localised source string and translate it to Python tokens.

    Args:
        source: Raw source text in the target local language.
        adapter: The loaded Adapter for the active language.

    Example::

        lexer = OrmLexer(source, adapter)
        tokens = lexer.tokenize()
    """

    def __init__(self, source: str, adapter: Adapter) -> None:
        self._source = source
        self._adapter = adapter
        forward_map = {
            **adapter.keyword_map,
            **adapter.builtin_map,
        }
        self._combined_map: dict[str, str] = {
            normalize_hudhaa(v): k for k, v in forward_map.items()
        }
        self._scanner = _build_scanner(
            tuple(sorted(w for w in self._combined_map if HUDHAA in w))
        )
        self._name_re = re.compile(_NAME)

    # ── Public API ───────────────────────────────────────────────────────────

    def tokenize(self) -> list[py_tokenize.TokenInfo]:
        """Tokenise the source and return a translated token list.

        Returns:
            List of TokenInfo where local-language NAME tokens have been
            replaced with their Python equivalents. The list always ends
            with NEWLINE (if needed), DEDENT tokens and ENDMARKER.

        Raises:
            OrmLexError: If the source cannot be tokenised.
        """
        with gc_paused():
            return self._tokenize()

    def _tokenize(self) -> list[py_tokenize.TokenInfo]:
        # Python treats \r\n and \r as a newline. Do the same, once.
        source = self._source.replace("\r\n", "\n").replace("\r", "\n")
        if source.startswith("\ufeff"):
            source = source[1:]  # a byte order mark is not code
        nul = source.find("\x00")
        if nul >= 0:
            raise self._fail("Lexer error: '\\x00'", source, nul)
        lines = source.split("\n")
        # Each token keeps a reference to its line. Build the texts once, or a
        # very long line would be copied again for every token on it.
        line_texts = [line + "\n" for line in lines]
        if not source.endswith("\n"):
            line_texts[-1] = lines[-1]
        scanner = self._scanner
        mapping = self._combined_map
        tokens: list[py_tokenize.TokenInfo] = []
        append = tokens.append
        TokenInfo = py_tokenize.TokenInfo

        pos = 0
        end = len(source)
        line_no = 1
        line_start = 0
        brackets: list[tuple[str, int, int]] = []  # open brackets: char, line, col
        indents = [0]
        alt_indents = [0]  # the same levels, counting a tab as one column
        at_line_start = True
        pending_newline = False  # a logical line has content but no NEWLINE yet

        while pos < end:
            if at_line_start and not brackets:
                pos, line_no, line_start, blank = self._handle_indent(
                    source,
                    pos,
                    line_no,
                    line_start,
                    line_texts,
                    indents,
                    alt_indents,
                    tokens,
                )
                if blank:
                    # Blank or comment-only line: the helper consumed it.
                    continue
                at_line_start = False

            match = scanner.match(source, pos)
            if match is None:
                self._raise_at(source, pos, line_no, line_start)
            kind = match.lastgroup
            text = match.group()
            col = pos - line_start
            line_text = line_texts[line_no - 1]

            if kind == "ws":
                pos = match.end()
                continue
            if kind == "comment":
                append(
                    TokenInfo(
                        COMMENT,
                        text,
                        (line_no, col),
                        (line_no, col + len(text)),
                        line_text,
                    )
                )
                pos = match.end()
                continue
            if kind == "newline":
                if brackets:
                    append(
                        TokenInfo(
                            NL, "\n", (line_no, col), (line_no, col + 1), line_text
                        )
                    )
                else:
                    if pending_newline:
                        append(
                            TokenInfo(
                                NEWLINE,
                                "\n",
                                (line_no, col),
                                (line_no, col + 1),
                                line_text,
                            )
                        )
                        pending_newline = False
                    at_line_start = True
                pos = match.end()
                line_no += 1
                line_start = pos
                continue
            if kind == "cont":
                pos = match.end()
                if pos >= end:
                    raise self._fail(CONTINUATION_EOF, source, end)
                line_no += 1
                line_start = pos
                continue
            # Real token: the logical line now has content.
            pending_newline = True
            # A single-quoted f-string may hold a newline inside a field (Python
            # 3.12), which the string pattern cannot match. Scan it by hand.
            forced_f = (
                kind == "name"
                and text.lower() in _F_PREFIXES
                and source[match.end() : match.end() + 1] in ("'", '"')
            )
            if kind == "string" or forced_f:
                string_end = match.end()
                if forced_f or _is_fstring(text):
                    string_end, text = self._scan_fstring(source, pos)
                raw_text = source[pos:string_end]
                new_lines = raw_text.count("\n")
                start = (line_no, col)
                if new_lines:
                    last_nl = raw_text.rfind("\n")
                    end_pos = (line_no + new_lines, len(raw_text) - last_nl - 1)
                else:
                    end_pos = (line_no, col + len(raw_text))
                append(TokenInfo(STRING, text, start, end_pos, line_text))
                pos = string_end
                if new_lines:
                    line_no += new_lines
                    line_start = source.rfind("\n", 0, pos) + 1
                continue
            if kind == "number":
                append(
                    TokenInfo(
                        NUMBER,
                        text,
                        (line_no, col),
                        (line_no, col + len(text)),
                        line_text,
                    )
                )
            elif kind == "name" or kind == "hudhaa":
                if kind == "hudhaa":
                    text = normalize_hudhaa(text)
                elif not text.isidentifier():
                    bad = _first_invalid_character(text)
                    self._raise_at(source, pos + bad, line_no, line_start)
                elif not text.isascii():
                    # Python compares identifiers in NFKC form.
                    text = unicodedata.normalize("NFKC", text)
                py_text = mapping.get(text, text)
                append(
                    TokenInfo(
                        NAME,
                        py_text,
                        (line_no, col),
                        (line_no, col + len(match.group())),
                        line_text,
                    )
                )
            else:  # operator
                if text in _OPENERS:
                    brackets.append((text, line_no, col))
                elif text in _CLOSERS and brackets:
                    brackets.pop()
                append(
                    TokenInfo(
                        OP, text, (line_no, col), (line_no, col + len(text)), line_text
                    )
                )
            pos = match.end()

        return self._finish(tokens, brackets, pending_newline, indents, line_no, lines)

    # ── Indentation ──────────────────────────────────────────────────────────

    def _handle_indent(
        self,
        source: str,
        pos: int,
        line_no: int,
        line_start: int,
        line_texts: list[str],
        indents: list[int],
        alt_indents: list[int],
        tokens: list[py_tokenize.TokenInfo],
    ) -> tuple[int, int, int, bool]:
        """Measure the indentation at ``pos`` and emit INDENT/DEDENT tokens.

        Returns ``(pos, line_no, line_start, blank)``. For a code line, ``pos``
        is the first non-blank character. For a blank or comment-only line,
        the line's tokens are emitted, ``blank`` is True and ``pos`` is the
        start of the next line. A backslash at the start of a line counts as
        indentation whitespace, as it does in CPython.
        """
        end = len(source)
        column = 0
        alt_column = 0
        # CPython: a backslash inside the indentation fixes the level at the
        # column of the first backslash that is not at column 0.
        fixed_column = 0
        scan = pos
        while scan < end:
            ch = source[scan]
            if ch == " ":
                column += 1
                alt_column += 1
            elif ch == "\t":
                column = (column // _TAB_SIZE + 1) * _TAB_SIZE
                alt_column += 1
            elif ch == "\f":
                column = alt_column = 0
            elif ch == "\\" and source.startswith("\\\n", scan):
                scan += 1  # the newline is skipped below
                line_no += 1
                line_start = scan + 1
                fixed_column = fixed_column or column
                if line_start >= end:
                    raise self._fail(CONTINUATION_EOF, source, end)
            else:
                break
            scan += 1
        if fixed_column:
            column = alt_column = fixed_column

        line_text = line_texts[line_no - 1]
        if scan >= end or source[scan] in "#\n":
            # Blank line or comment-only line: no INDENT/DEDENT.
            nl_pos = source.find("\n", scan)
            stop = end if nl_pos < 0 else nl_pos
            col = scan - line_start
            if scan < end and source[scan] == "#":
                comment = source[scan:stop]
                tokens.append(
                    py_tokenize.TokenInfo(
                        COMMENT,
                        comment,
                        (line_no, col),
                        (line_no, col + len(comment)),
                        line_text,
                    )
                )
                col += len(comment)
            if stop < end:
                tokens.append(
                    py_tokenize.TokenInfo(
                        NL, "\n", (line_no, col), (line_no, col + 1), line_text
                    )
                )
            return (stop + 1 if stop < end else end + 1), line_no + 1, stop + 1, True

        if column > indents[-1]:
            if alt_column <= alt_indents[-1]:
                raise self._tab_error(line_no, scan - line_start)
            indents.append(column)
            alt_indents.append(alt_column)
            tokens.append(
                py_tokenize.TokenInfo(
                    INDENT,
                    source[line_start:scan],
                    (line_no, 0),
                    (line_no, scan - line_start),
                    line_text,
                )
            )
        else:
            while column < indents[-1]:
                indents.pop()
                alt_indents.pop()
                tokens.append(
                    py_tokenize.TokenInfo(
                        DEDENT,
                        "",
                        (line_no, scan - line_start),
                        (line_no, scan - line_start),
                        line_text,
                    )
                )
            if column != indents[-1]:
                raise OrmLexError(
                    code="E0001",
                    message="Unindent does not match any outer indentation level",
                    orm_line=line_no,
                    orm_col=scan - line_start + 1,
                    lang=self._adapter.lang,
                )
            if alt_column != alt_indents[-1]:
                raise self._tab_error(line_no, scan - line_start)
        return scan, line_no, line_start, False

    def _tab_error(self, line_no: int, col: int) -> OrmLexError:
        return OrmLexError(
            code="E0001",
            message="Inconsistent use of tabs and spaces in indentation",
            orm_line=line_no,
            orm_col=col + 1,
            lang=self._adapter.lang,
        )

    # ── End of input ─────────────────────────────────────────────────────────

    def _finish(
        self,
        tokens: list[py_tokenize.TokenInfo],
        brackets: list[tuple[str, int, int]],
        pending_newline: bool,
        indents: list[int],
        line_no: int,
        lines: list[str],
    ) -> list[py_tokenize.TokenInfo]:
        if brackets:
            char, open_line, open_col = brackets[-1]
            raise OrmLexError(
                code="E0001",
                message=f"'{char}' was never closed",
                orm_line=open_line,
                orm_col=open_col + 1,
                lang=self._adapter.lang,
            )
        # line_no is the line after the last one that was read, unless the
        # last line had no newline at its end.
        end_line = line_no if pending_newline else line_no - 1
        if pending_newline:
            col = len(lines[-1])
            tokens.append(
                py_tokenize.TokenInfo(
                    NEWLINE, "", (end_line, col), (end_line, col + 1), ""
                )
            )
        for _ in indents[1:]:
            tokens.append(
                py_tokenize.TokenInfo(
                    DEDENT, "", (end_line + 1, 0), (end_line + 1, 0), ""
                )
            )
        tokens.append(
            py_tokenize.TokenInfo(
                ENDMARKER, "", (end_line + 1, 0), (end_line + 1, 0), ""
            )
        )
        return tokens

    # ── Errors ───────────────────────────────────────────────────────────────

    def _raise_at(
        self, source: str, pos: int, line_no: int, line_start: int
    ) -> NoReturn:
        char = source[pos]
        if char in "\"'":
            message = "Unterminated string literal"
        else:
            message = f"Lexer error: {char!r}"
        raise OrmLexError(
            code="E0001",
            message=message,
            orm_line=line_no,
            orm_col=pos - line_start + 1,
            lang=self._adapter.lang,
        )

    # ── f-strings ────────────────────────────────────────────────────────────

    def _translate_name(self, name: str) -> str:
        return self._combined_map.get(normalize_hudhaa(name), name)

    def _fail(self, message: str, source: str, pos: int) -> OrmLexError:
        line_no = source.count("\n", 0, pos) + 1
        col = pos - (source.rfind("\n", 0, pos) + 1)
        return OrmLexError(
            code="E0001",
            message=message,
            orm_line=line_no,
            orm_col=col + 1,
            lang=self._adapter.lang,
        )

    def _scan_fstring(self, source: str, pos: int) -> tuple[int, str]:
        """Scan an f-string that starts at ``pos``.

        Names inside ``{...}`` fields are translated. Fields may hold strings
        that use the same quote as the f-string (allowed since Python 3.12),
        so a plain regular expression cannot find the end of the literal.

        Returns:
            (index after the closing quote, translated literal text)
        """
        n = len(source)
        j = pos
        while source[j] not in "\"'":
            j += 1
        prefix = source[pos:j]
        raw = "r" in prefix or "R" in prefix
        quote = source[j]
        delim = quote * 3 if source.startswith(quote * 3, j) else quote
        k = j + len(delim)
        out = [source[pos:k]]
        while k < n:
            if source.startswith(delim, k):
                out.append(delim)
                return k + len(delim), "".join(out)
            ch = source[k]
            if ch == "\\":
                nxt = source[k + 1 : k + 2]
                if nxt in ("{", "}", ""):
                    out.append(ch)
                    k += 1
                elif nxt == "N" and not raw and source[k + 2 : k + 3] == "{":
                    close = source.find("}", k)
                    if close < 0:
                        break
                    out.append(source[k : close + 1])
                    k = close + 1
                else:
                    out.append(source[k : k + 2])
                    k += 2
            elif ch == "{":
                if source.startswith("{{", k):
                    out.append("{{")
                    k += 2
                else:
                    k = self._scan_field(source, k + 1, out, delim)
            elif ch == "\n" and len(delim) == 1:
                break
            else:
                out.append(ch)
                k += 1
        raise self._fail("Unterminated string literal", source, pos)

    def _scan_field(self, source: str, k: int, out: list[str], delim: str) -> int:
        """Scan one replacement field; ``k`` is just after its ``{``.

        Appends the translated text, starting with the ``{``, to ``out`` and
        returns the index after the closing ``}``.
        """
        n = len(source)
        out.append("{")
        depth = 0
        in_spec = False
        seen_field = False
        while k < n:
            ch = source[k]
            if in_spec:
                if source.startswith(delim, k):
                    # The closing quote of the f-string ends it, also here.
                    raise self._fail("Unterminated f-string field", source, k)
                if ch == "{":
                    if seen_field and source.startswith("{{", k):
                        # Python 3.12: "{{" is an escape only after a field in
                        # the spec (see oromscript.fstrings).
                        out.append("{{")
                        k += 2
                    else:
                        k = self._scan_field(source, k + 1, out, delim)
                        seen_field = True
                    continue
                out.append(ch)
                k += 1
                if ch == "}":
                    return k
                continue
            if ch in "\"'":
                end = self._skip_plain_string(source, k)
                out.append(source[k:end])
                k = end
            elif ch in "([{":
                depth += 1
                out.append(ch)
                k += 1
            elif ch in ")]}":
                out.append(ch)
                k += 1
                if depth == 0:
                    return k
                depth -= 1
            elif ch == ":" and depth == 0:
                in_spec = True
                out.append(ch)
                k += 1
            elif ch == "!" and depth == 0 and source[k + 1 : k + 2] != "=":
                out.append(ch)
                k += 1
                while k < n and source[k].isalpha():
                    out.append(source[k])
                    k += 1
            elif ch.isalpha() or ch == "_":
                k = self._scan_word(source, k, out)
            else:
                out.append(ch)
                k += 1
        raise self._fail("Unterminated f-string field", source, k - 1)

    def _scan_word(self, source: str, k: int, out: list[str]) -> int:
        """Translate the name at ``k`` inside an f-string field."""
        match = self._name_re.match(source, k)
        assert match is not None  # noqa: S101
        word = match.group()
        end = match.end()
        nxt = source[end : end + 1]
        if nxt in ("'", '"') and word.lower() in _STRING_PREFIXES:
            # A string with a prefix, for example rb"..." or f"..." in a field.
            if "f" in word.lower():
                string_end, text = self._scan_fstring(source, k)
                out.append(text)
                return string_end
            string_end = self._skip_plain_string(source, end)
            out.append(source[k:string_end])
            return string_end
        # A hudhaa inside a known keyword, for example walitti_ida'i
        while source[end : end + 1] in tuple(HUDHAA_VARIANTS):
            more = self._name_re.match(source, end + 1)
            if more is None:
                break
            candidate = word + HUDHAA + more.group()
            if normalize_hudhaa(candidate) not in self._combined_map:
                break
            word = candidate
            end = more.end()
        out.append(self._translate_name(word))
        return end

    @staticmethod
    def _skip_plain_string(source: str, k: int) -> int:
        """Return the index after the (non-f) string literal that starts at ``k``."""
        quote = source[k]
        delim = quote * 3 if source.startswith(quote * 3, k) else quote
        j = k + len(delim)
        n = len(source)
        while j < n:
            if source[j] == "\\":
                j += 2
            elif source.startswith(delim, j):
                return j + len(delim)
            else:
                j += 1
        return n
