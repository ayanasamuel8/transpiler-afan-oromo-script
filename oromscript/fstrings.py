"""
oromscript.fstrings
~~~~~~~~~~~~~~~~~~~
Builds the ``JoinedStr`` tree for an f-string (or several strings next to each
other, at least one of them an f-string).

The text of a replacement field is handed to a callback, so the parser can
read it with the same recursive descent rules as the rest of the program.
This module only cuts the text into literal pieces and fields. It follows the
rules of CPython, including the Python 3.12 rules (PEP 701) when it runs on
3.12 or newer.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Callable

from .strings import _decode_escapes, decode_string_literal, split_literal

#: Python 3.12 lets a field hold backslashes, comments, newlines and the quote
#: that ends the f-string. Older versions reject all of these.
_PEP_701 = sys.version_info >= (3, 12)
# A format spec may hold fields. Python 3.12 allows them two levels deep, older
# versions one level.
_MAX_NESTING = 3 if _PEP_701 else 2
# Only Python 3.12 decodes the escapes in the format spec of a raw f-string.
_DECODE_RAW_SPEC = (3, 12) <= sys.version_info < (3, 13)
# Python 3.12 gives kind "u" to any text that starts with a u"..." string. Older
# versions do it only for the very first text of the whole string.
_U_KIND_ANYWHERE = _PEP_701

ExprParser = Callable[[str], ast.expr]


class FStringError(ValueError):
    """The f-string is not valid."""


class _UText(str):
    """Text that comes from a ``u"..."`` string. Its ``Constant`` has kind "u"."""


def build_joined_str(
    tokens: list[tuple[str, int]], parse_expression: ExprParser
) -> ast.JoinedStr:
    """Return the ``JoinedStr`` for string tokens that include an f-string.

    Args:
        tokens: ``(token text, line number)`` for each string, in order.
        parse_expression: Turns the text of a field expression into a tree.

    Raises:
        FStringError: If an f-string is not valid.
    """
    pieces: list[str | ast.FormattedValue] = []
    first_is_u = split_literal(tokens[0][0])[0] == "u"
    if _U_KIND_ANYWHERE:
        top_mode = spec_mode = "marked"
    else:
        top_mode = "all" if first_is_u else "none"
        spec_mode = "before_field" if first_is_u else "none"
    for text, lineno in tokens:
        prefix, body = split_literal(text)
        lowered = prefix.lower()
        if "b" in lowered:
            raise FStringError("cannot mix bytes and nonbytes literals")
        if "f" not in lowered:
            value = decode_string_literal(text, lineno)
            assert isinstance(value, str)  # noqa: S101
            pieces.append(_UText(value) if prefix == "u" else value)
            continue
        quote = text[len(prefix)]
        triple = text[len(prefix) : len(prefix) + 3] == quote * 3
        scanner = _Scanner(
            body, "r" in lowered, quote, triple, lineno, parse_expression, spec_mode
        )
        scanner.run(pieces)
    return ast.JoinedStr(values=_merge(pieces, top_mode))


def _merge(pieces: list[str | ast.FormattedValue], mode: str) -> list[ast.expr]:
    """Join neighbouring text pieces into ``Constant`` nodes.

    ``mode`` says which ``Constant`` nodes get kind "u", as in CPython:
    ``marked`` (Python 3.12): those whose text starts with text from a ``u``
    string. ``all``: every one. ``before_field``: those followed by a field.
    ``none``: none.
    """
    values: list[ast.expr] = []
    buffer: list[str] = []

    def flush(followed_by_field: bool) -> None:
        text = "".join(buffer)
        if text:
            if mode == "marked":
                is_u = isinstance(buffer[0], _UText)
            else:
                is_u = mode == "all" or (mode == "before_field" and followed_by_field)
            kind = "u" if is_u else None
            values.append(ast.Constant(value=text, kind=kind))
        buffer.clear()

    for piece in pieces:
        if isinstance(piece, str):
            # Even an empty string counts: the first piece decides the kind.
            buffer.append(piece)
        else:
            flush(True)
            values.append(piece)
    flush(False)
    return values


class _Scanner:
    """Cuts the body of one f-string token into text and fields."""

    def __init__(
        self,
        body: str,
        raw: bool,
        quote: str,
        triple: bool,
        lineno: int,
        parse_expression: ExprParser,
        spec_mode: str,
    ) -> None:
        self.s = body
        self.raw = raw
        self.quote = quote
        self.triple = triple
        self.lineno = lineno
        self.parse_expression = parse_expression
        self.spec_mode = spec_mode

    def run(self, pieces: list[str | ast.FormattedValue]) -> None:
        self.text_and_fields(0, pieces, nesting=0)

    # ── Text and fields ──────────────────────────────────────────────────────

    def text_and_fields(
        self, i: int, pieces: list[str | ast.FormattedValue], *, nesting: int
    ) -> int:
        """Scan literal text and fields from ``i``.

        At the top level this runs to the end of the body. In a format spec
        (``nesting`` above 0) it stops at the ``}`` that closes the field and
        returns its index.
        """
        s = self.s
        n = len(s)
        in_spec = nesting > 0
        text: list[str] = []
        seen_field = False

        def flush() -> None:
            if text:
                joined = "".join(text)
                if not self.raw or (in_spec and _DECODE_RAW_SPEC):
                    joined = _decode_escapes(joined, False, self.lineno)
                pieces.append(joined)
                text.clear()

        while i < n:
            ch = s[i]
            if ch == "\\":
                nxt = s[i + 1 : i + 2]
                if nxt == "N" and not self.raw and s[i + 2 : i + 3] == "{":
                    close = s.find("}", i)
                    if close < 0:
                        raise FStringError("malformed \\N character escape")
                    text.append(s[i : close + 1])
                    i = close + 1
                elif nxt and nxt not in "{}":
                    text.append(s[i : i + 2])
                    i += 2
                else:
                    text.append(ch)
                    i += 1
            elif ch == "{":
                if not in_spec and s[i + 1 : i + 2] == "{":
                    text.append("{")
                    i += 2
                elif in_spec and _PEP_701 and seen_field and s[i + 1 : i + 2] == "{":
                    # Python 3.12 reads "{{" in a format spec as the escape for a
                    # "{" only after a field in that spec. Before that, it starts
                    # a field whose expression begins with "{".
                    text.append("{")
                    i += 2
                else:
                    flush()
                    i = self.field(i + 1, pieces, nesting)
                    seen_field = True
            elif ch == "}":
                if in_spec:
                    flush()
                    return i
                if s[i + 1 : i + 2] == "}":
                    text.append("}")
                    i += 2
                else:
                    raise FStringError("single '}' is not allowed")
            else:
                text.append(ch)
                i += 1
        flush()
        if in_spec:
            raise FStringError("expecting '}'")
        return i

    # ── One replacement field ────────────────────────────────────────────────

    def field(
        self, i: int, pieces: list[str | ast.FormattedValue], nesting: int
    ) -> int:
        """Read the field that starts at ``i`` (just after its ``{``).

        Returns the index after the closing ``}``.
        """
        s = self.s
        if nesting >= _MAX_NESTING:
            raise FStringError("expressions nested too deeply")
        start = i
        j = self.expression_end(i)
        expression = s[start:j]
        if not expression.strip():
            raise FStringError("empty expression not allowed")
        self.check_old_rules(expression)

        debug_text = None
        if s[j : j + 1] == "=":
            j += 1
            while s[j : j + 1] in (" ", "\t", "\n", "\r", "\f"):
                j += 1
            debug_text = self.without_comments(s[start:j])

        conversion = -1
        if s[j : j + 1] == "!":
            letter = s[j + 1 : j + 2]
            if letter not in ("s", "r", "a"):
                raise FStringError("invalid conversion character")
            conversion = ord(letter)
            j += 2
            while _PEP_701 and s[j : j + 1] in (" ", "\t", "\n", "\r", "\f"):
                j += 1
            if s[j : j + 1] not in (":", "}"):
                raise FStringError("expecting ':' or '}'")

        spec = None
        if s[j : j + 1] == ":":
            spec_pieces: list[str | ast.FormattedValue] = []
            j = self.text_and_fields(j + 1, spec_pieces, nesting=nesting + 1)
            spec = ast.JoinedStr(values=_merge(spec_pieces, self.spec_mode))
        # Here s[j] is the "}" that closes the field: every path above ends on it.

        if debug_text is not None:
            pieces.append(debug_text)
            if conversion == -1 and spec is None:
                conversion = ord("r")
        value = self.parse_expression(expression)
        pieces.append(
            ast.FormattedValue(value=value, conversion=conversion, format_spec=spec)
        )
        return j + 1

    def expression_end(self, i: int) -> int:
        """Return the index where the expression that starts at ``i`` ends."""
        s = self.s
        n = len(s)
        depth = 0
        j = i
        while j < n:
            c = s[j]
            if c in "'\"":
                j = self.skip_string(j)
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    if c == "}":
                        return j
                    raise FStringError(f"unmatched '{c}'")
                depth -= 1
            elif depth == 0:
                if c == "!" and s[j + 1 : j + 2] != "=":
                    return j
                if c == ":":
                    return j
                if c == "=" and self.is_debug_marker(j):
                    return j
            j += 1
        raise FStringError("expecting '}'")

    def without_comments(self, text: str) -> str:
        """Remove ``# ...`` comments (outside strings) from the text of ``{x=}``."""
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            c = text[i]
            if c in "'\"":
                end = self.skip_string_in(text, i)
                out.append(text[i:end])
                i = end
            elif c == "#":
                while i < n and text[i] != "\n":
                    i += 1
            else:
                out.append(c)
                i += 1
        return "".join(out)

    @staticmethod
    def skip_string_in(text: str, j: int) -> int:
        quote = text[j]
        delim = quote * 3 if text.startswith(quote * 3, j) else quote
        k = j + len(delim)
        while k < len(text):
            if text[k] == "\\":
                k += 2
            elif text.startswith(delim, k):
                return k + len(delim)
            else:
                k += 1
        return len(text)

    def is_debug_marker(self, j: int) -> bool:
        """Is the ``=`` at ``j`` the self-documenting ``=`` of ``{x=}``?"""
        s = self.s
        if s[j + 1 : j + 2] == "=" or s[j - 1 : j] in ("=", "!", "<", ">"):
            return False
        k = j + 1
        while s[k : k + 1] in (" ", "\t", "\n", "\r", "\f"):
            k += 1
        return s[k : k + 1] in ("!", ":", "}")

    def skip_string(self, j: int) -> int:
        """Return the index after the string literal that starts at ``j``."""
        s = self.s
        quote = s[j]
        delim = quote * 3 if s.startswith(quote * 3, j) else quote
        k = j + len(delim)
        n = len(s)
        while k < n:
            if s[k] == "\\":
                k += 2
            elif s.startswith(delim, k):
                return k + len(delim)
            else:
                k += 1
        raise FStringError("unterminated string")

    def check_old_rules(self, expression: str) -> None:
        """Python before 3.12 does not allow these inside a field."""
        if _PEP_701:
            return
        if "\\" in expression:
            raise FStringError("a backslash is not allowed in an expression")
        if "#" in expression:
            raise FStringError("'#' is not allowed in an expression")
        if (self.quote * 3 if self.triple else self.quote) in expression:
            raise FStringError("the quote of the f-string cannot be used inside it")
        if "\n" in expression and not self.triple:
            raise FStringError("a newline is not allowed in an expression")
