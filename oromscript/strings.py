"""
oromscript.strings
~~~~~~~~~~~~~~~~~~
Decodes the text of a Python string or bytes literal into its value.

Python's ``ast.literal_eval`` would do this, but it parses the text a second
time and reports warnings (for example for ``"\\d"``) with a useless location.
It also changes the global warning filters, which is not safe with threads.
This module does the work directly and reports warnings at the ``.orm`` line.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import warnings

_ESCAPE = re.compile(
    r"\\(\n|[\\'\"abfnrtv]|[0-7]{1,3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}"
    r"|U[0-9a-fA-F]{8}|N\{[^}\n]*\}|.)",
    re.DOTALL,
)
_SIMPLE = {
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
_WARNING = SyntaxWarning if sys.version_info >= (3, 12) else DeprecationWarning
_TRUNCATED = {
    "x": "truncated \\xXX escape",
    "u": "truncated \\uXXXX escape",
    "U": "truncated \\UXXXXXXXX escape",
    "N": "malformed \\N character escape",
}


def split_literal(text: str) -> tuple[str, str]:
    """Split a string token into its prefix letters and its body (no quotes)."""
    first_quote = 0 if text[0] in "\"'" else (1 if text[1] in "\"'" else 2)
    prefix = text[:first_quote]
    rest = text[first_quote:]
    width = 3 if rest[:3] in ('"""', "'''") else 1
    return prefix, rest[width:-width]


def decode_string_literal(text: str, lineno: int) -> str | bytes:
    """Return the value of one (non f-string) string or bytes token.

    Args:
        text: The token text, with prefix and quotes.
        lineno: Line in the ``.orm`` source, used for warnings.

    Raises:
        ValueError: If the literal is not valid, for example ``"\\x4"``.
    """
    prefix, body = split_literal(text)
    prefix = prefix.lower()
    is_bytes = "b" in prefix
    if is_bytes and not body.isascii():
        raise ValueError("bytes can only contain ASCII literal characters")
    if "r" not in prefix and "\\" in body:
        body = _decode_escapes(body, is_bytes, lineno)
    return body.encode("latin-1") if is_bytes else body


def _decode_escapes(body: str, is_bytes: bool, lineno: int) -> str:
    def replace(match: re.Match[str]) -> str:
        code = match.group(1)
        if code == "\n":
            return ""
        simple = _SIMPLE.get(code)
        if simple is not None:
            return simple
        head = code[0]
        if head in "01234567":
            value = int(code, 8)
            if value > 0o377:
                if sys.version_info >= (3, 12):
                    warnings.warn_explicit(
                        f"invalid octal escape sequence '\\{code}'",
                        _WARNING,
                        "<orm>",
                        lineno,
                    )
                if is_bytes:
                    value &= 0xFF
            return chr(value)
        if head == "x" and len(code) == 3:
            return chr(int(code[1:], 16))
        if not is_bytes and head in "uU" and len(code) > 1:
            value = int(code[1:], 16)
            if value > 0x10FFFF:
                raise ValueError("illegal Unicode character")
            return chr(value)
        if not is_bytes and head == "N" and len(code) > 1:
            try:
                return unicodedata.lookup(code[2:-1])
            except KeyError:
                raise ValueError(
                    f"unknown Unicode character name: {code[2:-1]}"
                ) from None
        if head in "xuUN" and len(code) == 1 and (head == "x" or not is_bytes):
            raise ValueError(_TRUNCATED[head])
        warnings.warn_explicit(
            f"invalid escape sequence '\\{code[0]}'", _WARNING, "<orm>", lineno
        )
        if head == "N" and len(code) > 1:
            # Bytes have no \N{...}. Escapes inside the braces still count.
            return "\\N" + _decode_escapes(code[1:], is_bytes, lineno)
        return "\\" + code

    return _ESCAPE.sub(replace, body)
