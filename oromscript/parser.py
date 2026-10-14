"""
oromscript.parser
~~~~~~~~~~~~~~~~~
A hand-written recursive descent parser.

It reads the translated token stream from :mod:`oromscript.lexer` and builds
a standard Python ``ast`` tree. Expressions use precedence climbing, and
statements use one method per grammar rule.

This is the second stage of the OromScript transpile pipeline.
"""

from __future__ import annotations
import __future__

import ast
import functools
import keyword
import sys
import tokenize
from typing import Any, NoReturn, TypeVar, cast

from ._gc import gc_paused
from .adapter import Adapter
from .errors import OrmError, OrmSyntaxError
from .fstrings import FStringError, build_joined_str
from .graphemes import grapheme_nodes
from .lexer import OrmLexer
from .strings import decode_string_literal, split_literal

_N = TypeVar("_N", bound=ast.AST)

NAME = tokenize.NAME
NUMBER = tokenize.NUMBER
STRING = tokenize.STRING
OP = tokenize.OP
NEWLINE = tokenize.NEWLINE
INDENT = tokenize.INDENT
DEDENT = tokenize.DEDENT
ENDMARKER = tokenize.ENDMARKER

_KEYWORDS = frozenset(keyword.kwlist)
_PosType = tuple[int, int]

_BINARY_PRECEDENCE: dict[str, int] = {
    "|": 1,
    "^": 2,
    "&": 3,
    "<<": 4,
    ">>": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
    "//": 6,
    "%": 6,
    "@": 6,
}
_BINARY_OPS: dict[str, ast.operator] = {
    "|": ast.BitOr(),
    "^": ast.BitXor(),
    "&": ast.BitAnd(),
    "<<": ast.LShift(),
    ">>": ast.RShift(),
    "+": ast.Add(),
    "-": ast.Sub(),
    "*": ast.Mult(),
    "/": ast.Div(),
    "//": ast.FloorDiv(),
    "%": ast.Mod(),
    "@": ast.MatMult(),
}
_AUG_OPS: dict[str, ast.operator] = {
    "|=": ast.BitOr(),
    "^=": ast.BitXor(),
    "&=": ast.BitAnd(),
    "<<=": ast.LShift(),
    ">>=": ast.RShift(),
    "+=": ast.Add(),
    "-=": ast.Sub(),
    "*=": ast.Mult(),
    "/=": ast.Div(),
    "//=": ast.FloorDiv(),
    "%=": ast.Mod(),
    "@=": ast.MatMult(),
    "**=": ast.Pow(),
}
_COMPARE_OPS: dict[str, ast.cmpop] = {
    "<": ast.Lt(),
    ">": ast.Gt(),
    "==": ast.Eq(),
    ">=": ast.GtE(),
    "<=": ast.LtE(),
    "!=": ast.NotEq(),
}
_UNARY_OPS: dict[str, ast.unaryop] = {
    "+": ast.UAdd(),
    "-": ast.USub(),
    "~": ast.Invert(),
}
_CONSTANTS: dict[str, Any] = {"True": True, "False": False, "None": None}
# Tokens after which an optional expression (return, yield) is absent.
_EXPR_END_OPS = frozenset({")", "]", "}", ";", "=", ":", ","})
# CPython shares one object for each context and operator, and so do we.
_LOAD = ast.Load()
_STORE = ast.Store()
_DEL = ast.Del()
_IN, _IS, _IS_NOT, _NOT_IN = ast.In(), ast.Is(), ast.IsNot(), ast.NotIn()
_USUB, _NOT, _POW, _OR, _AND = ast.USub(), ast.Not(), ast.Pow(), ast.Or(), ast.And()
_COMPOUND_KEYWORDS = frozenset(
    {"if", "while", "for", "try", "with", "def", "class", "async", "match"}
)
_SIMPLE_KEYWORDS = frozenset(
    {
        "pass", "break", "continue", "return", "raise", "global", "nonlocal",
        "del", "assert", "import", "from", "type",
    }
)  # fmt: skip
# Operators after which an expression cannot continue.
_STOP_OPS = frozenset({")", "]", "}", ",", ":", ";", "=", ":=", "->", *_AUG_OPS})
_KEYWORDS_AND_YIELD_FROM = _KEYWORDS | {"yield from"}
_HAS_TYPE_PARAMS = "type_params" in ast.FunctionDef._fields
_HAS_TYPE_PARAM_DEFAULTS = _HAS_TYPE_PARAMS and (
    "default_value" in getattr(ast, "TypeVar")._fields  # noqa: B009
)
# Python 3.14 allows "except A, B:" without brackets.
_BARE_EXCEPT_TUPLE = sys.version_info >= (3, 14)
# Python 3.14 checks the names in "from __future__ import ..." while parsing.
_CHECK_FUTURE = sys.version_info >= (3, 14)
# Python 3.11 allows a starred expression in a subscript: a[*b].
_STAR_IN_SUBSCRIPT = sys.version_info >= (3, 11)


def _extra(**fields: Any) -> dict[str, Any]:
    """Return fields that only exist on newer Python versions."""
    return fields if _HAS_TYPE_PARAMS else {}


class _Parser:
    """One parse of one token list. Not reusable."""

    def __init__(self, tokens: list[tokenize.TokenInfo], adapter: Adapter) -> None:
        self._toks = [
            t for t in tokens if t.type not in (tokenize.COMMENT, tokenize.NL)
        ]
        if not self._toks or self._toks[-1].type != ENDMARKER:
            end = self._toks[-1].end if self._toks else (1, 0)
            self._toks.append(tokenize.TokenInfo(ENDMARKER, "", end, end, ""))
        self._i = 0
        self._tok = self._toks[0]
        self._last = self._tok
        self._lang = adapter.lang

    # ── Token helpers ────────────────────────────────────────────────────────

    def _advance(self) -> tokenize.TokenInfo:
        tok = self._tok
        if tok.type not in (NEWLINE, INDENT, DEDENT, ENDMARKER):
            self._last = tok
        if tok.type != ENDMARKER:
            self._i += 1
            self._tok = self._toks[self._i]
        return tok

    def _peek(self, n: int = 1) -> tokenize.TokenInfo:
        idx = self._i + n
        return self._toks[idx] if idx < len(self._toks) else self._toks[-1]

    def _error(
        self, message: str = "invalid syntax", tok: tokenize.TokenInfo | None = None
    ) -> NoReturn:
        tok = tok or self._tok
        line, col = tok.start[0], tok.start[1] + 1
        text = tok.line
        if tok.line == "" and self._last is not tok:
            # A token made up at the end of the input has no line of its own.
            # Report the end of the last real token instead, as Python does.
            line, col = self._last.end[0], self._last.end[1] + 1
            text = self._last.line
        raise OrmSyntaxError(
            code="E0010",
            message=message,
            orm_line=line,
            orm_col=col,
            lang=self._lang,
            context={"text": text.rstrip("\n")},
        )

    def _is_op(self, value: str) -> bool:
        tok = self._tok
        return tok.type == OP and tok.string == value

    def _is_kw(self, value: str) -> bool:
        tok = self._tok
        return tok.type == NAME and tok.string == value

    def _accept_op(self, value: str) -> bool:
        tok = self._tok
        if tok.type == OP and tok.string == value:
            self._advance()
            return True
        return False

    def _accept_kw(self, value: str) -> bool:
        tok = self._tok
        if tok.type == NAME and tok.string == value:
            self._advance()
            return True
        return False

    def _expect_op(self, value: str) -> tokenize.TokenInfo:
        if not self._is_op(value):
            self._error(f"expected '{value}'")
        return self._advance()

    def _expect_kw(self, value: str) -> tokenize.TokenInfo:
        if not self._is_kw(value):
            self._error(f"expected '{value}'")
        return self._advance()

    def _expect_name(self) -> tokenize.TokenInfo:
        tok = self._tok
        if tok.type != NAME or tok.string in _KEYWORDS or tok.string == "yield from":
            self._error("expected a name")
        return self._advance()

    def _at(self, node: _N, start: _PosType) -> _N:
        """Set the source position of ``node``: from ``start`` to the last token."""
        n: Any = node
        n.lineno, n.col_offset = start
        n.end_lineno, n.end_col_offset = self._last.end
        return node

    def _stmt(self, node: Any, start: _PosType) -> ast.stmt:
        """Like ``_at`` for nodes made through a version-dependent class."""
        return cast(ast.stmt, self._at(node, start))

    # ── Entry point ──────────────────────────────────────────────────────────

    def fstring_expression(self) -> ast.expr:
        """Parse the text of one f-string field (the tokens end with NEWLINE)."""
        if self._is_kw("yield") or self._is_kw("yield from"):
            value = self._yield_expr()
        else:
            value = self._star_expressions()
        if isinstance(value, ast.Starred):
            self._error("cannot use a starred expression here")
        if self._tok.type not in (NEWLINE, ENDMARKER):
            self._error()
        return value

    def parse_module(self) -> ast.Module:
        body: list[ast.stmt] = []
        while self._tok.type != ENDMARKER:
            if self._tok.type == NEWLINE:
                self._advance()
                continue
            if self._tok.type in (INDENT, DEDENT):
                self._error("unexpected indent")
            body.extend(self._statement())
        return ast.Module(body=body, type_ignores=[])

    # ── Statements ───────────────────────────────────────────────────────────

    def _statement(self) -> list[ast.stmt]:
        tok = self._tok
        if tok.type == NAME:
            name = tok.string
            if name not in _COMPOUND_KEYWORDS:
                return self._simple_stmts()
            if name == "if":
                return [self._if_stmt()]
            if name == "while":
                return [self._while_stmt()]
            if name == "for":
                return [self._for_stmt(tok.start, is_async=False)]
            if name == "try":
                return [self._try_stmt()]
            if name == "with":
                return [self._with_stmt(tok.start, is_async=False)]
            if name == "def":
                return [self._funcdef([], tok.start, is_async=False)]
            if name == "class":
                return [self._classdef([])]
            if name == "async":
                return [self._async_stmt([])]
            if name == "match":
                matched = self._try_match_stmt()
                if matched is not None:
                    return [matched]
        elif tok.type == OP and tok.string == "@":
            return [self._decorated()]
        return self._simple_stmts()

    def _block(self) -> list[ast.stmt]:
        """Parse ``':' (simple_stmts | NEWLINE INDENT statements DEDENT)``."""
        self._expect_op(":")
        if self._tok.type != NEWLINE:
            return self._simple_stmts()
        self._advance()
        if self._tok.type != INDENT:
            self._error("expected an indented block")
        self._advance()
        body: list[ast.stmt] = []
        while self._tok.type not in (DEDENT, ENDMARKER):
            if self._tok.type == NEWLINE:
                self._advance()
                continue
            if self._tok.type == INDENT:
                self._error("unexpected indent")
            body.extend(self._statement())
        if self._tok.type == DEDENT:
            self._advance()
        return body

    def _simple_stmts(self) -> list[ast.stmt]:
        stmts = [self._simple_stmt()]
        while self._accept_op(";"):
            if self._tok.type == NEWLINE:
                break
            stmts.append(self._simple_stmt())
        if self._tok.type == NEWLINE:
            self._advance()
        elif self._tok.type != ENDMARKER:
            self._error()
        return stmts

    def _simple_stmt(self) -> ast.stmt:
        tok = self._tok
        start = tok.start
        if tok.type == NAME and tok.string in _SIMPLE_KEYWORDS:
            name = tok.string
            if name == "pass":
                self._advance()
                return self._at(ast.Pass(), start)
            if name == "break":
                self._advance()
                return self._at(ast.Break(), start)
            if name == "continue":
                self._advance()
                return self._at(ast.Continue(), start)
            if name == "return":
                self._advance()
                value = None if self._at_expr_end() else self._star_expressions()
                return self._at(ast.Return(value=value), start)
            if name == "raise":
                return self._raise_stmt()
            if name == "global" or name == "nonlocal":
                self._advance()
                names = [self._expect_name().string]
                while self._accept_op(","):
                    names.append(self._expect_name().string)
                cls = ast.Global if name == "global" else ast.Nonlocal
                return self._at(cls(names=names), start)
            if name == "del":
                return self._del_stmt()
            if name == "assert":
                self._advance()
                test = self._expression()
                msg = self._expression() if self._accept_op(",") else None
                return self._at(ast.Assert(test=test, msg=msg), start)
            if name == "import":
                return self._import_stmt()
            if name == "from":
                return self._from_stmt()
            if name == "type" and self._is_type_alias():
                return self._type_alias()
        return self._expr_or_assign()

    def _at_expr_end(self) -> bool:
        tok = self._tok
        if tok.type in (NEWLINE, ENDMARKER):
            return True
        return tok.type == OP and tok.string in _EXPR_END_OPS

    def _raise_stmt(self) -> ast.stmt:
        start = self._advance().start
        exc = cause = None
        if not self._at_expr_end():
            exc = self._expression()
            if self._accept_kw("from"):
                cause = self._expression()
        return self._at(ast.Raise(exc=exc, cause=cause), start)

    def _del_stmt(self) -> ast.stmt:
        start = self._advance().start
        targets: list[ast.expr] = []
        while True:
            target = self._bitor_expr()
            self._set_context(target, _DEL, "delete")
            targets.append(target)
            if not self._accept_op(","):
                break
            if self._at_expr_end():
                break
        return self._at(ast.Delete(targets=targets), start)

    def _dotted_name(self) -> str:
        parts = [self._expect_name().string]
        while self._is_op(".") and self._peek().type == NAME:
            self._advance()
            parts.append(self._expect_name().string)
        return ".".join(parts)

    def _import_stmt(self) -> ast.stmt:
        start = self._advance().start
        names: list[ast.alias] = []
        while True:
            alias_start = self._tok.start
            name = self._dotted_name()
            asname = self._expect_name().string if self._accept_kw("as") else None
            names.append(
                _with_graphemes(
                    self._at(ast.alias(name=name, asname=asname), alias_start), name
                )
            )
            if not self._accept_op(","):
                break
        return self._at(ast.Import(names=names), start)

    def _from_stmt(self) -> ast.stmt:
        start = self._advance().start
        level = 0
        while self._tok.type == OP and self._tok.string in (".", "..."):
            level += len(self._advance().string)
        module: str | None = None
        if not self._is_kw("import"):
            module = self._dotted_name()
        elif level == 0:
            self._error()
        self._expect_kw("import")
        names: list[ast.alias] = []
        if self._is_op("*"):
            alias_start = self._advance().start
            names.append(self._at(ast.alias(name="*", asname=None), alias_start))
        else:
            paren = self._accept_op("(")
            while True:
                alias_start = self._tok.start
                name = self._expect_name().string
                asname = self._expect_name().string if self._accept_kw("as") else None
                names.append(
                    _with_graphemes(
                        self._at(ast.alias(name=name, asname=asname), alias_start), name
                    )
                )
                if not self._accept_op(","):
                    break
                if paren and self._is_op(")"):
                    break
            if paren:
                self._expect_op(")")
        if _CHECK_FUTURE and module == "__future__" and level == 0:
            for alias in names:
                if alias.name == "braces":
                    self._error("not a chance", self._toks[self._i - 1])
                if alias.name not in __future__.all_feature_names:
                    self._error(f"future feature {alias.name} is not defined")
        return self._at(ast.ImportFrom(module=module, names=names, level=level), start)

    def _expr_or_assign(self) -> ast.stmt:
        first = self._tok
        start = first.start
        first_is_paren = first.type == OP and first.string == "("
        if first.type == NAME and (
            first.string == "yield" or first.string == "yield from"
        ):
            value: ast.expr = self._yield_expr()
        else:
            value = self._star_expressions()
        tok = self._tok
        if tok.type == OP:
            op = tok.string
            if op == "=":
                targets = [value]
                while self._accept_op("="):
                    if self._is_kw("yield") or self._is_kw("yield from"):
                        value = self._yield_expr()
                    else:
                        value = self._star_expressions()
                    targets.append(value)
                value = targets.pop()
                for target in targets:
                    self._set_context(target, _STORE, "assign to")
                return self._at(
                    ast.Assign(targets=targets, value=value, type_comment=None), start
                )
            if op in _AUG_OPS:
                if not isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)):
                    self._error("illegal target for augmented assignment")
                self._set_context(value, _STORE, "assign to")
                self._advance()
                if self._is_kw("yield") or self._is_kw("yield from"):
                    rhs: ast.expr = self._yield_expr()
                else:
                    rhs = self._star_expressions()
                return self._at(
                    ast.AugAssign(target=value, op=_AUG_OPS[op], value=rhs), start
                )
            if op == ":":
                if not isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)):
                    self._error("illegal target for annotation")
                self._set_context(value, _STORE, "assign to")
                self._advance()
                annotation = self._expression()
                rhs_opt: ast.expr | None = None
                if self._accept_op("="):
                    if self._is_kw("yield") or self._is_kw("yield from"):
                        rhs_opt = self._yield_expr()
                    else:
                        rhs_opt = self._star_expressions()
                simple = 1 if isinstance(value, ast.Name) and not first_is_paren else 0
                return self._at(
                    ast.AnnAssign(
                        target=value,
                        annotation=annotation,
                        value=rhs_opt,
                        simple=simple,
                    ),
                    start,
                )
        return self._at(ast.Expr(value=value), start)

    def _set_context(self, node: ast.expr, ctx: ast.expr_context, verb: str) -> None:
        if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript)):
            node.ctx = ctx
        elif isinstance(node, ast.Starred) and not isinstance(ctx, ast.Del):
            node.ctx = ctx
            self._set_context(node.value, ctx, verb)
        elif isinstance(node, (ast.Tuple, ast.List)):
            node.ctx = ctx
            for elt in node.elts:
                self._set_context(elt, ctx, verb)
        else:
            raise OrmSyntaxError(
                code="E0010",
                message=f"cannot {verb} {type(node).__name__.lower()}",
                orm_line=getattr(node, "lineno", 0),
                orm_col=getattr(node, "col_offset", 0) + 1,
                lang=self._lang,
                context={"text": self._tok.line.rstrip("\n")},
            )

    # ── Compound statements ──────────────────────────────────────────────────

    def _if_stmt(self) -> ast.If:
        start = self._advance().start  # 'if' or 'elif'
        test = self._named_expression()
        body = self._block()
        orelse: list[ast.stmt] = []
        if self._is_kw("elif"):
            orelse = [self._if_stmt()]
        elif self._accept_kw("else"):
            orelse = self._block()
        return self._at(ast.If(test=test, body=body, orelse=orelse), start)

    def _while_stmt(self) -> ast.While:
        start = self._advance().start
        test = self._named_expression()
        body = self._block()
        orelse = self._block() if self._accept_kw("else") else []
        return self._at(ast.While(test=test, body=body, orelse=orelse), start)

    def _for_stmt(self, start: _PosType, *, is_async: bool) -> ast.stmt:
        self._expect_kw("for")
        target = self._target_list()
        self._expect_kw("in")
        iter_ = self._star_expressions()
        body = self._block()
        orelse = self._block() if self._accept_kw("else") else []
        cls: Any = ast.AsyncFor if is_async else ast.For
        return self._stmt(
            cls(
                target=target,
                iter=iter_,
                body=body,
                orelse=orelse,
                type_comment=None,
            ),
            start,
        )

    def _try_stmt(self) -> ast.stmt:
        start = self._advance().start
        body = self._block()
        handlers: list[ast.ExceptHandler] = []
        star = False
        while self._is_kw("except"):
            h_tok = self._advance()
            h_start = h_tok.start
            h_star = self._accept_op("*")
            if handlers and h_star != star:
                self._error(
                    "cannot have both 'except' and 'except*' on the same try", h_tok
                )
            star = h_star
            type_: ast.expr | None = None
            name: str | None = None
            if self._is_op(":"):
                if star:
                    self._error("'except*' needs an exception type")
            else:
                type_start = self._tok.start
                type_ = self._expression()
                bare_tuple = False
                if _BARE_EXCEPT_TUPLE and self._is_op(","):
                    bare_tuple = True
                    elts = [type_]
                    while self._accept_op(","):
                        elts.append(self._expression())
                    type_ = self._at(ast.Tuple(elts=elts, ctx=_LOAD), type_start)
                if self._is_kw("as"):
                    if bare_tuple:
                        self._error("multiple exception types must be in brackets")
                    self._advance()
                    name = self._expect_name().string
            h_body = self._block()
            handlers.append(
                _with_graphemes(
                    self._at(
                        ast.ExceptHandler(type=type_, name=name, body=h_body), h_start
                    ),
                    name,
                )
            )
        orelse: list[ast.stmt] = []
        finalbody: list[ast.stmt] = []
        if handlers and self._accept_kw("else"):
            orelse = self._block()
        if self._accept_kw("finally"):
            finalbody = self._block()
        if not handlers and not finalbody:
            self._error("expected 'except' or 'finally' block")
        if star and not hasattr(ast, "TryStar"):
            self._error("'except*' needs Python 3.11 or newer")
        cls: Any = getattr(ast, "TryStar") if star else ast.Try  # noqa: B009
        return self._stmt(
            cls(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody),
            start,
        )

    def _with_stmt(self, start: _PosType, *, is_async: bool) -> ast.stmt:
        self._expect_kw("with")
        items: list[ast.withitem] | None = None
        if self._is_op("("):
            items = self._try_parenthesized_with_items()
        if items is None:
            items = [self._with_item()]
            while self._accept_op(","):
                items.append(self._with_item())
        body = self._block()
        cls: Any = ast.AsyncWith if is_async else ast.With
        return self._stmt(cls(items=items, body=body, type_comment=None), start)

    def _try_parenthesized_with_items(self) -> list[ast.withitem] | None:
        """Try ``with (a as b, c as d):``. Backtrack if it is a plain expression."""
        saved = (self._i, self._tok, self._last)
        try:
            self._expect_op("(")
            items = [self._with_item()]
            while self._accept_op(","):
                if self._is_op(")"):
                    break
                items.append(self._with_item())
            self._expect_op(")")
            if not self._is_op(":"):
                raise OrmSyntaxError(code="E0010", message="backtrack", lang=self._lang)
            return items
        except OrmSyntaxError:
            self._i, self._tok, self._last = saved
            return None

    def _with_item(self) -> ast.withitem:
        expr = self._expression()
        target = None
        if self._accept_kw("as"):
            target = self._star_target()
            self._set_context(target, _STORE, "assign to")
        return ast.withitem(context_expr=expr, optional_vars=target)

    def _async_stmt(self, decorators: list[ast.expr]) -> ast.stmt:
        start = self._advance().start  # 'async'
        if self._is_kw("def"):
            return self._funcdef(decorators, start, is_async=True)
        if decorators:
            self._error("expected 'def' after decorator")
        if self._is_kw("for"):
            return self._for_stmt(start, is_async=True)
        if self._is_kw("with"):
            return self._with_stmt(start, is_async=True)
        self._error("expected 'def', 'for' or 'with' after 'async'")

    def _decorated(self) -> ast.stmt:
        decorators: list[ast.expr] = []
        while self._is_op("@"):
            self._advance()
            decorators.append(self._named_expression())
            if self._tok.type != NEWLINE:
                self._error()
            self._advance()
        if self._is_kw("def"):
            return self._funcdef(decorators, self._tok.start, is_async=False)
        if self._is_kw("class"):
            return self._classdef(decorators)
        if self._is_kw("async"):
            return self._async_stmt(decorators)
        self._error("expected 'def' or 'class' after decorator")

    def _funcdef(
        self, decorators: list[ast.expr], start: _PosType, *, is_async: bool
    ) -> ast.stmt:
        self._expect_kw("def")
        name = self._expect_name().string
        type_params = self._type_params()
        self._expect_op("(")
        args = self._parameters(")", annotations=True)
        self._expect_op(")")
        returns = self._expression() if self._accept_op("->") else None
        body = self._block()
        cls: Any = ast.AsyncFunctionDef if is_async else ast.FunctionDef
        node = self._stmt(
            cls(
                name=name,
                args=args,
                body=body,
                decorator_list=decorators,
                returns=returns,
                type_comment=None,
                **_extra(type_params=type_params),
            ),
            start,
        )
        return _with_graphemes(node, name)

    def _classdef(self, decorators: list[ast.expr]) -> ast.stmt:
        start = self._advance().start
        name = self._expect_name().string
        type_params = self._type_params()
        bases: list[ast.expr] = []
        keywords: list[ast.keyword] = []
        if self._accept_op("("):
            bases, keywords = self._call_arguments()
            self._expect_op(")")
        body = self._block()
        node = self._at(
            ast.ClassDef(
                name=name,
                bases=bases,
                keywords=keywords,
                body=body,
                decorator_list=decorators,
                **_extra(type_params=type_params),
            ),
            start,
        )
        return _with_graphemes(node, name)

    # ── Type parameters and type aliases (Python 3.12+) ──────────────────────

    def _type_params(self) -> list[ast.AST]:
        if not self._is_op("["):
            return []
        if not _HAS_TYPE_PARAMS:
            self._error("type parameter syntax needs Python 3.12 or newer")
        self._advance()
        if self._is_op("]"):
            self._error("type parameter list cannot be empty")
        params: list[ast.AST] = []
        while not self._is_op("]"):
            start = self._tok.start
            kind = "typevar"
            if self._accept_op("*"):
                kind = "tuple"
            elif self._accept_op("**"):
                kind = "spec"
            name = self._expect_name().string
            bound = None
            if kind == "typevar" and self._accept_op(":"):
                bound = self._expression()
            fields: dict[str, Any] = {}
            if _HAS_TYPE_PARAM_DEFAULTS:
                default = None
                if self._accept_op("="):
                    default = (
                        self._star_expression()
                        if kind == "tuple"
                        else self._expression()
                    )
                fields["default_value"] = default
            elif self._is_op("="):
                self._error("type parameter defaults need Python 3.13 or newer")
            if kind == "typevar":
                node: Any = getattr(ast, "TypeVar")(  # noqa: B009
                    name=name, bound=bound, **fields
                )
            elif kind == "tuple":
                node = getattr(ast, "TypeVarTuple")(name=name, **fields)  # noqa: B009
            else:
                node = getattr(ast, "ParamSpec")(name=name, **fields)  # noqa: B009
            params.append(self._at(node, start))
            if not self._accept_op(","):
                break
        self._expect_op("]")
        return params

    def _is_type_alias(self) -> bool:
        if not _HAS_TYPE_PARAMS:
            return False
        nxt = self._peek()
        after = self._peek(2)
        return (
            nxt.type == NAME
            and nxt.string not in _KEYWORDS
            and after.type == OP
            and after.string in ("[", "=")
        )

    def _type_alias(self) -> ast.stmt:
        start = self._advance().start  # 'type'
        tok = self._expect_name()
        name = self._at(_name(tok.string, _STORE), tok.start)
        type_params = self._type_params()
        self._expect_op("=")
        value = self._expression()
        alias: Any = getattr(ast, "TypeAlias")(  # noqa: B009
            name=name, type_params=type_params, value=value
        )
        return self._stmt(alias, start)

    # ── Parameters ───────────────────────────────────────────────────────────

    def _parameters(self, closer: str, *, annotations: bool) -> ast.arguments:
        posonly: list[ast.arg] = []
        args: list[ast.arg] = []
        defaults: list[ast.expr] = []
        kwonly: list[ast.arg] = []
        kw_defaults: list[ast.expr | None] = []
        vararg: ast.arg | None = None
        kwarg: ast.arg | None = None
        seen_star = False
        seen_slash = False
        seen_default = False
        while not self._is_op(closer):
            if self._is_op("/"):
                if seen_slash or seen_star or not args:
                    self._error("invalid position for '/'")
                self._advance()
                posonly, args = args, []
                seen_slash = True
            elif self._is_op("*"):
                if seen_star:
                    self._error("duplicate '*' in parameters")
                self._advance()
                seen_star = True
                if not self._is_op(","):
                    vararg = self._parameter(annotations, star=True)
                elif self._peek().type == OP and self._peek().string in (
                    closer,
                    "**",
                ):
                    self._error("named arguments must follow bare *")
            elif self._is_op("**"):
                self._advance()
                kwarg = self._parameter(annotations)
                self._accept_op(",")
                if not self._is_op(closer):
                    self._error("arguments cannot follow var-keyword argument")
                break
            else:
                param = self._parameter(annotations)
                default = self._expression() if self._accept_op("=") else None
                if seen_star:
                    kwonly.append(param)
                    kw_defaults.append(default)
                else:
                    if default is not None:
                        seen_default = True
                        defaults.append(default)
                    elif seen_default:
                        self._error("non-default argument follows default argument")
                    args.append(param)
            if not self._accept_op(","):
                break
        return ast.arguments(
            posonlyargs=posonly,
            args=args,
            vararg=vararg,
            kwonlyargs=kwonly,
            kw_defaults=kw_defaults,
            kwarg=kwarg,
            defaults=defaults,
        )

    def _parameter(self, annotations: bool, *, star: bool = False) -> ast.arg:
        tok = self._expect_name()
        annotation = None
        if annotations and self._accept_op(":"):
            if star and self._is_op("*"):
                if not _STAR_IN_SUBSCRIPT:
                    self._error("a starred annotation needs Python 3.11")
                annotation = self._star_expression()
            else:
                annotation = self._expression()
        return _with_graphemes(
            self._at(
                ast.arg(arg=tok.string, annotation=annotation, type_comment=None),
                tok.start,
            ),
            tok.string,
        )

    # ── match statement ──────────────────────────────────────────────────────

    def _try_match_stmt(self) -> ast.stmt | None:
        """Parse a ``match`` statement, or return None if ``match`` is a name."""
        saved = (self._i, self._tok, self._last)
        start = self._tok.start
        try:
            self._advance()
            subject = self._match_subject()
            self._expect_op(":")
            if self._tok.type != NEWLINE:
                raise OrmSyntaxError(code="E0010", message="no", lang=self._lang)
            self._advance()
            if self._tok.type != INDENT or not (
                self._peek().type == NAME and self._peek().string == "case"
            ):
                raise OrmSyntaxError(code="E0010", message="no", lang=self._lang)
            self._advance()
        except OrmSyntaxError:
            self._i, self._tok, self._last = saved
            return None
        cases: list[ast.match_case] = []
        while self._is_kw("case"):
            cases.append(self._match_case())
        if self._tok.type == DEDENT:
            self._advance()
        elif self._tok.type != ENDMARKER:
            self._error("expected 'case'")
        return self._at(ast.Match(subject=subject, cases=cases), start)

    def _match_subject(self) -> ast.expr:
        start = self._tok.start
        first = self._star_named_expression()
        if self._is_op(","):
            elts = [first]
            while self._accept_op(","):
                if self._is_op(":"):
                    break
                elts.append(self._star_named_expression())
            return self._at(ast.Tuple(elts=elts, ctx=_LOAD), start)
        if isinstance(first, ast.Starred):
            self._error("cannot use a starred expression here")
        return first

    def _match_case(self) -> ast.match_case:
        self._advance()  # 'case'
        pattern = self._patterns()
        guard = self._named_expression() if self._accept_kw("if") else None
        body = self._block()
        return ast.match_case(pattern=pattern, guard=guard, body=body)

    def _patterns(self) -> ast.pattern:
        start = self._tok.start
        first = self._maybe_star_pattern()
        if self._is_op(","):
            items = [first]
            while self._accept_op(","):
                if self._is_op(":") or self._is_kw("if"):
                    break
                items.append(self._maybe_star_pattern())
            return self._at(ast.MatchSequence(patterns=items), start)
        if isinstance(first, ast.MatchStar):
            self._error("star pattern cannot be used alone")
        return first

    def _maybe_star_pattern(self) -> ast.pattern:
        if self._is_op("*"):
            start = self._advance().start
            name = self._expect_name().string
            return self._at(ast.MatchStar(name=None if name == "_" else name), start)
        return self._as_pattern()

    def _as_pattern(self) -> ast.pattern:
        start = self._tok.start
        pattern = self._or_pattern()
        if self._accept_kw("as"):
            tok = self._expect_name()
            if tok.string == "_":
                self._error("cannot use '_' as a target", tok)
            return self._at(ast.MatchAs(pattern=pattern, name=tok.string), start)
        return pattern

    def _or_pattern(self) -> ast.pattern:
        start = self._tok.start
        first = self._closed_pattern()
        if not self._is_op("|"):
            return first
        alternatives = [first]
        while self._accept_op("|"):
            alternatives.append(self._closed_pattern())
        return self._at(ast.MatchOr(patterns=alternatives), start)

    def _closed_pattern(self) -> ast.pattern:
        tok = self._tok
        start = tok.start
        if tok.type == NUMBER or (tok.type == OP and tok.string == "-"):
            return self._at(ast.MatchValue(value=self._signed_number()), start)
        if tok.type == STRING:
            return self._at(ast.MatchValue(value=self._strings()), start)
        if tok.type == NAME:
            word = tok.string
            if word in _CONSTANTS:
                self._advance()
                return self._at(ast.MatchSingleton(value=_CONSTANTS[word]), start)
            nxt = self._peek()
            dotted = nxt.type == OP and nxt.string == "."
            called = nxt.type == OP and nxt.string == "("
            if not dotted and not called:
                self._expect_name()
                name = None if word == "_" else word
                return self._at(ast.MatchAs(pattern=None, name=name), start)
            value: ast.expr = self._at(_name(self._expect_name().string, _LOAD), start)
            while self._accept_op("."):
                attr = self._expect_name().string
                value = self._at(_attribute(value, attr, _LOAD), start)
            if self._is_op("("):
                return self._class_pattern(value, start)
            return self._at(ast.MatchValue(value=value), start)
        if tok.type == OP:
            if tok.string == "(":
                return self._group_or_sequence_pattern()
            if tok.string == "[":
                self._advance()
                items = self._pattern_items("]")
                self._expect_op("]")
                return self._at(ast.MatchSequence(patterns=items), start)
            if tok.string == "{":
                return self._mapping_pattern()
        self._error()

    def _signed_number(self) -> ast.expr:
        start = self._tok.start
        negative = self._accept_op("-")
        tok = self._tok
        if tok.type != NUMBER:
            self._error("expected a number")
        number = self._number()
        if negative:
            number = self._at(ast.UnaryOp(op=_USUB, operand=number), start)
        if self._tok.type == OP and self._tok.string in ("+", "-"):
            if tok.string[-1] in "jJ":
                self._error("the real part of a complex pattern must be real")
            op = self._advance().string
            if self._tok.type != NUMBER or self._tok.string[-1] not in "jJ":
                self._error("expected an imaginary number")
            right = self._number()
            number = self._at(
                ast.BinOp(left=number, op=_BINARY_OPS[op], right=right), start
            )
        return number

    def _group_or_sequence_pattern(self) -> ast.pattern:
        start = self._advance().start  # '('
        if self._is_op(")"):
            self._advance()
            return self._at(ast.MatchSequence(patterns=[]), start)
        first = self._maybe_star_pattern()
        if self._is_op(")") and not isinstance(first, ast.MatchStar):
            self._advance()
            return first
        if isinstance(first, ast.MatchStar) and not self._is_op(","):
            self._error("star pattern needs a comma in brackets")
        items = [first]
        while self._accept_op(","):
            if self._is_op(")"):
                break
            items.append(self._maybe_star_pattern())
        self._expect_op(")")
        return self._at(ast.MatchSequence(patterns=items), start)

    def _pattern_items(self, closer: str) -> list[ast.pattern]:
        items: list[ast.pattern] = []
        while not self._is_op(closer):
            items.append(self._maybe_star_pattern())
            if not self._accept_op(","):
                break
        return items

    def _mapping_pattern(self) -> ast.pattern:
        start = self._advance().start  # '{'
        keys: list[ast.expr] = []
        patterns: list[ast.pattern] = []
        rest: str | None = None
        while not self._is_op("}"):
            if self._accept_op("**"):
                rest_tok = self._expect_name()
                if rest_tok.string == "_":
                    self._error("'_' cannot be the rest of a mapping pattern", rest_tok)
                rest = rest_tok.string
                self._accept_op(",")
                if not self._is_op("}"):
                    self._error("rest pattern must be last")
                break
            keys.append(self._mapping_key())
            self._expect_op(":")
            patterns.append(self._as_pattern())
            if not self._accept_op(","):
                break
        self._expect_op("}")
        return self._at(
            ast.MatchMapping(keys=keys, patterns=patterns, rest=rest), start
        )

    def _mapping_key(self) -> ast.expr:
        tok = self._tok
        start = tok.start
        if tok.type == NUMBER or (tok.type == OP and tok.string == "-"):
            return self._signed_number()
        if tok.type == STRING:
            return self._strings()
        if tok.type == NAME:
            if tok.string in _CONSTANTS:
                self._advance()
                return self._at(
                    ast.Constant(value=_CONSTANTS[tok.string], kind=None), start
                )
            value: ast.expr = self._at(_name(self._expect_name().string, _LOAD), start)
            if not self._is_op("."):
                self._error("mapping keys must be literals or dotted names")
            while self._accept_op("."):
                attr = self._expect_name().string
                value = self._at(_attribute(value, attr, _LOAD), start)
            return value
        self._error()

    def _class_pattern(self, cls: ast.expr, start: _PosType) -> ast.pattern:
        self._expect_op("(")
        patterns: list[ast.pattern] = []
        kwd_attrs: list[str] = []
        kwd_patterns: list[ast.pattern] = []
        while not self._is_op(")"):
            nxt = self._peek()
            if self._tok.type == NAME and nxt.type == OP and nxt.string == "=":
                kwd_attrs.append(self._expect_name().string)
                self._advance()
                kwd_patterns.append(self._as_pattern())
            else:
                if kwd_attrs:
                    self._error("positional patterns follow keyword patterns")
                patterns.append(self._as_pattern())
            if not self._accept_op(","):
                break
        self._expect_op(")")
        return self._at(
            ast.MatchClass(
                cls=cls,
                patterns=patterns,
                kwd_attrs=kwd_attrs,
                kwd_patterns=kwd_patterns,
            ),
            start,
        )

    # ── Targets ──────────────────────────────────────────────────────────────

    def _star_target(self) -> ast.expr:
        start = self._tok.start
        if self._accept_op("*"):
            value = self._bitor_expr()
            return self._at(ast.Starred(value=value, ctx=_STORE), start)
        return self._bitor_expr()

    def _target_list(self) -> ast.expr:
        """Parse the targets of ``for``/comprehensions up to the ``in`` keyword."""
        start = self._tok.start
        first = self._star_target()
        if self._is_op(","):
            elts = [first]
            while self._accept_op(","):
                if self._is_kw("in"):
                    break
                elts.append(self._star_target())
            first = self._at(ast.Tuple(elts=elts, ctx=_STORE), start)
        self._set_context(first, _STORE, "assign to")
        return first

    # ── Expressions ──────────────────────────────────────────────────────────

    def _star_expressions(self) -> ast.expr:
        start = self._tok.start
        first = self._star_expression()
        if not self._is_op(","):
            return first
        elts = [first]
        while self._accept_op(","):
            if self._at_expr_end():
                break
            elts.append(self._star_expression())
        return self._at(ast.Tuple(elts=elts, ctx=_LOAD), start)

    def _star_expression(self) -> ast.expr:
        if self._is_op("*"):
            start = self._advance().start
            value = self._bitor_expr()
            return self._at(ast.Starred(value=value, ctx=_LOAD), start)
        return self._expression()

    def _star_named_expression(self) -> ast.expr:
        if self._is_op("*"):
            start = self._advance().start
            value = self._bitor_expr()
            return self._at(ast.Starred(value=value, ctx=_LOAD), start)
        return self._named_expression()

    def _named_expression(self) -> ast.expr:
        tok = self._tok
        if tok.type == NAME and tok.string not in _KEYWORDS:
            nxt = self._peek()
            if nxt.type == OP and nxt.string == ":=":
                self._advance()
                self._advance()
                target = self._at(_name(tok.string, _STORE), tok.start)
                # position of target covers only the name
                target.end_lineno, target.end_col_offset = tok.end
                value = self._expression()
                return self._at(ast.NamedExpr(target=target, value=value), tok.start)
        return self._expression()

    def _expression(self) -> ast.expr:
        tok = self._tok
        start = tok.start
        if tok.type == NAME:
            word = tok.string
            if word == "lambda":
                return self._lambda()
            if word == "not":
                return self._ternary_rest(self._disjunction(), start)
        left = self._unary()
        # Most operands are followed by a closing bracket, a comma, or the end
        # of the line. Skip the levels for "or", "and", comparisons and "if".
        nxt = self._tok
        kind = nxt.type
        if kind == OP:
            if nxt.string in _STOP_OPS:
                return left
        elif kind != NAME:
            return left
        return self._ternary_rest(self._disjunction_rest(left, start), start)

    def _ternary_rest(self, body: ast.expr, start: _PosType) -> ast.expr:
        tok = self._tok
        if tok.type == NAME and tok.string == "if":
            self._advance()
            test = self._disjunction()
            self._expect_kw("else")
            orelse = self._expression()
            return self._at(ast.IfExp(test=test, body=body, orelse=orelse), start)
        return body

    def _lambda(self) -> ast.expr:
        start = self._advance().start
        args = self._parameters(":", annotations=False)
        self._expect_op(":")
        body = self._expression()
        return self._at(ast.Lambda(args=args, body=body), start)

    def _yield_expr(self) -> ast.expr:
        tok = self._advance()
        start = tok.start
        if tok.string == "yield from" or self._accept_kw("from"):
            value = self._expression()
            return self._at(ast.YieldFrom(value=value), start)
        if self._at_expr_end():
            return self._at(ast.Yield(value=None), start)
        return self._at(ast.Yield(value=self._star_expressions()), start)

    def _disjunction(self) -> ast.expr:
        start = self._tok.start
        return self._disjunction_rest(self._conjunction(), start)

    def _disjunction_rest(self, left: ast.expr, start: _PosType) -> ast.expr:
        """Finish an expression whose first operand ``left`` is already parsed.

        Runs the comparison, ``and`` and ``or`` levels, in that order.
        """
        first = self._conjunction_rest(
            self._comparison_rest(self._binary_rest(left, start, 1), start), start
        )
        if not self._is_kw("or"):
            return first
        values = [first]
        while self._accept_kw("or"):
            values.append(self._conjunction())
        return self._at(ast.BoolOp(op=_OR, values=values), start)

    def _conjunction(self) -> ast.expr:
        start = self._tok.start
        return self._conjunction_rest(self._inversion(), start)

    def _conjunction_rest(self, first: ast.expr, start: _PosType) -> ast.expr:
        if not self._is_kw("and"):
            return first
        values = [first]
        while self._accept_kw("and"):
            values.append(self._inversion())
        return self._at(ast.BoolOp(op=_AND, values=values), start)

    def _inversion(self) -> ast.expr:
        if self._is_kw("not"):
            start = self._advance().start
            operand = self._inversion()
            return self._at(ast.UnaryOp(op=_NOT, operand=operand), start)
        return self._comparison()

    def _comparison(self) -> ast.expr:
        start = self._tok.start
        return self._comparison_rest(self._binary(1), start)

    def _comparison_rest(self, left: ast.expr, start: _PosType) -> ast.expr:
        ops: list[ast.cmpop] = []
        comparators: list[ast.expr] = []
        while True:
            tok = self._tok
            if tok.type == OP:
                cls = _COMPARE_OPS.get(tok.string)
                if cls is None:
                    break
                self._advance()
                ops.append(cls)
            elif tok.type == NAME:
                word = tok.string
                if word == "in":
                    self._advance()
                    ops.append(_IN)
                elif word == "is":
                    self._advance()
                    ops.append(_IS_NOT if self._accept_kw("not") else _IS)
                elif word == "not" and self._peek().string == "in":
                    self._advance()
                    self._advance()
                    ops.append(_NOT_IN)
                else:
                    break
            else:
                break
            comparators.append(self._binary(1))
        if not ops:
            return left
        return self._at(ast.Compare(left=left, ops=ops, comparators=comparators), start)

    def _bitor_expr(self) -> ast.expr:
        return self._binary(1)

    def _binary(self, min_prec: int) -> ast.expr:
        start = self._tok.start
        return self._binary_rest(self._unary(), start, min_prec)

    def _binary_rest(self, left: ast.expr, start: _PosType, min_prec: int) -> ast.expr:
        while True:
            tok = self._tok
            if tok.type != OP:
                return left
            prec = _BINARY_PRECEDENCE.get(tok.string)
            if prec is None or prec < min_prec:
                return left
            self._advance()
            right = self._binary(prec + 1)
            left = self._at(
                ast.BinOp(left=left, op=_BINARY_OPS[tok.string], right=right),
                start,
            )

    def _unary(self) -> ast.expr:
        tok = self._tok
        if tok.type == OP:
            cls = _UNARY_OPS.get(tok.string)
            if cls is not None:
                self._advance()
                operand = self._unary()
                return self._at(ast.UnaryOp(op=cls, operand=operand), tok.start)
        return self._power()

    def _power(self) -> ast.expr:
        tok = self._tok
        start = tok.start
        if tok.type == NAME and tok.string == "await":
            self._advance()
            value: ast.expr = self._at(ast.Await(value=self._primary()), start)
        else:
            value = self._primary()
        nxt = self._tok
        if nxt.type == OP and nxt.string == "**":
            self._advance()
            right = self._unary()
            return self._at(ast.BinOp(left=value, op=_POW, right=right), start)
        return value

    def _primary(self) -> ast.expr:
        first = self._tok
        start = first.start
        if first.type == NAME and first.string not in _KEYWORDS_AND_YIELD_FROM:
            # The most common atom, a plain name. Same as _atom, without the calls.
            self._last = first
            self._i += 1
            self._tok = self._toks[self._i]
            node: ast.expr = _name(first.string, _LOAD)
            node.lineno, node.col_offset = start
            node.end_lineno, node.end_col_offset = first.end
        else:
            node = self._atom()
        while True:
            tok = self._tok
            if tok.type != OP:
                return node
            op = tok.string
            if op == ".":
                self._advance()
                attr = self._expect_name().string
                node = self._at(_attribute(node, attr, _LOAD), start)
            elif op == "(":
                paren = self._advance().start
                args, keywords = self._call_arguments(paren)
                self._expect_op(")")
                node = self._at(
                    ast.Call(func=node, args=args, keywords=keywords), start
                )
            elif op == "[":
                self._advance()
                index = self._slices()
                self._expect_op("]")
                node = self._at(
                    ast.Subscript(value=node, slice=index, ctx=_LOAD), start
                )
            else:
                return node

    def _call_arguments(
        self, open_paren: _PosType | None = None
    ) -> tuple[list[ast.expr], list[ast.keyword]]:
        """Parse call arguments up to (not including) the closing ``)``.

        ``open_paren`` is the position of the call's ``(``. It is given only
        for calls, where a sole generator expression is allowed.
        """
        args: list[ast.expr] = []
        keywords: list[ast.keyword] = []
        first = True
        while True:
            tok = self._tok
            kind = tok.type
            if kind == OP and tok.string == ")":
                break
            start = tok.start
            if kind == OP and tok.string == "*":
                self._advance()
                if any(k.arg is None for k in keywords):
                    self._error(
                        "iterable argument unpacking follows "
                        "keyword argument unpacking",
                        tok,
                    )
                value = self._expression()
                args.append(self._at(ast.Starred(value=value, ctx=_LOAD), start))
            elif kind == OP and tok.string == "**":
                self._advance()
                value = self._expression()
                keywords.append(self._at(ast.keyword(arg=None, value=value), start))
            elif (
                kind == NAME
                and tok.string not in _KEYWORDS
                and self._toks[self._i + 1].type == OP
                and self._toks[self._i + 1].string == "="
            ):
                self._advance()
                self._advance()
                value = self._expression()
                keywords.append(
                    _with_graphemes(
                        self._at(ast.keyword(arg=tok.string, value=value), start),
                        tok.string,
                    )
                )
            else:
                if keywords:
                    self._error("positional argument follows keyword argument", tok)
                value = self._named_expression()
                after = self._tok
                if after.type == NAME and (
                    after.string == "for" or after.string == "async"
                ):
                    if open_paren is None or not first:
                        self._error("generator expression must be parenthesized")
                    generators = self._comprehension_clauses(value)
                    if not self._is_op(")"):
                        self._error("generator expression must be parenthesized")
                    gen = ast.GeneratorExp(elt=value, generators=generators)
                    n: Any = gen
                    n.lineno, n.col_offset = open_paren
                    n.end_lineno, n.end_col_offset = self._tok.end
                    args.append(gen)
                    break
                args.append(value)
            first = False
            after = self._tok
            if after.type == OP and after.string == ",":
                self._advance()
            else:
                break
        return args, keywords

    def _slices(self) -> ast.expr:
        start = self._tok.start
        first = self._slice()
        if not self._is_op(","):
            if isinstance(first, ast.Starred):
                return self._at(ast.Tuple(elts=[first], ctx=_LOAD), start)
            return first
        elts = [first]
        while self._accept_op(","):
            if self._is_op("]"):
                break
            elts.append(self._slice())
        return self._at(ast.Tuple(elts=elts, ctx=_LOAD), start)

    def _slice(self) -> ast.expr:
        start = self._tok.start
        lower = upper = step = None
        if self._is_op("*"):
            if not _STAR_IN_SUBSCRIPT:
                self._error("starred expressions in subscripts need Python 3.11")
            star_start = self._advance().start
            value = self._expression()
            return self._at(ast.Starred(value=value, ctx=_LOAD), star_start)
        if not self._is_op(":"):
            first_tok = self._tok
            lower = self._named_expression()
            if not self._is_op(":"):
                return lower
            if isinstance(lower, ast.NamedExpr) and first_tok.string != "(":
                self._error("an assignment expression in a slice needs brackets")
        self._expect_op(":")
        if not self._slice_end():
            upper = self._expression()
        if self._accept_op(":") and not self._slice_end():
            step = self._expression()
        return self._at(ast.Slice(lower=lower, upper=upper, step=step), start)

    def _slice_end(self) -> bool:
        tok = self._tok
        return tok.type == OP and tok.string in (":", ",", "]")

    # ── Atoms ────────────────────────────────────────────────────────────────

    def _atom(self) -> ast.expr:
        tok = self._tok
        start = tok.start
        kind = tok.type
        if kind == NAME:
            word = tok.string
            if word in _CONSTANTS:
                self._advance()
                return self._at(ast.Constant(value=_CONSTANTS[word], kind=None), start)
            # Other keywords are errors. A plain name never gets here, because
            # _primary reads those itself.
            self._error()
        if kind == NUMBER:
            return self._number()
        if kind == STRING:
            return self._strings()
        if kind == OP:
            op = tok.string
            if op == "(":
                return self._paren_atom()
            if op == "[":
                return self._list_atom()
            if op == "{":
                return self._brace_atom()
            if op == "...":
                self._advance()
                return self._at(ast.Constant(value=Ellipsis, kind=None), start)
        self._error()

    def _number(self) -> ast.expr:
        tok = self._advance()
        text = tok.string
        if text.isdigit() and (text[0] != "0" or len(text) == 1) and len(text) < 4000:
            # The common case: a plain decimal integer.
            return self._at(ast.Constant(value=int(text), kind=None), tok.start)
        text = text.replace("_", "")
        value: Any
        if text[0] == "0" and text.isdigit() and text.strip("0"):
            self._error(
                "leading zeros in decimal integer literals are not permitted", tok
            )
        try:
            if text[-1] in "jJ":
                value = complex(text)
            elif text[:2].lower() in ("0x", "0o", "0b"):
                value = int(text, 0)
            elif "." in text or "e" in text or "E" in text:
                value = float(text)
            else:
                value = int(text, 10)
        except ValueError as exc:  # for example a number with too many digits
            self._error(f"invalid number: {exc}", tok)
        return self._at(ast.Constant(value=value, kind=None), tok.start)

    def _strings(self) -> ast.expr:
        first = self._tok
        start = first.start
        if self._peek().type != STRING:
            text = first.string
            quote = text[0]
            if (quote == '"' or quote == "'") and "\\" not in text:
                # The common case: one plain string with nothing to decode.
                triple = len(text) >= 6 and text[1] == quote and text[2] == quote
                width = 3 if triple else 1
                self._advance()
                return self._at(
                    ast.Constant(value=text[width:-width], kind=None), start
                )
        parts: list[tokenize.TokenInfo] = []
        while self._tok.type == STRING:
            parts.append(self._advance())
        if any("f" in _prefix(p.string).lower() for p in parts):
            return self._fstring(parts)
        values: list[str | bytes] = []
        for part in parts:
            values.append(self._string_value(part))
        if all(isinstance(v, str) for v in values):
            joined: str | bytes = "".join(values)  # type: ignore[arg-type]
        elif all(isinstance(v, bytes) for v in values):
            joined = b"".join(values)  # type: ignore[arg-type]
        else:
            self._error("cannot mix bytes and nonbytes literals", first)
        kind = "u" if _prefix(first.string) == "u" else None
        return self._at(ast.Constant(value=joined, kind=kind), start)

    def _string_value(self, tok: tokenize.TokenInfo) -> str | bytes:
        text = tok.string
        if "\\" not in text:
            prefix, body = split_literal(text)
            if prefix in ("", "u", "U"):
                return body  # the common case: nothing to decode
        try:
            return decode_string_literal(text, tok.start[0])
        except ValueError as exc:
            self._error(f"invalid string literal: {exc}", tok)

    def _fstring(self, parts: list[tokenize.TokenInfo]) -> ast.expr:
        """Build the tree for strings next to each other, at least one an f-string."""
        tokens = [(p.string, p.start[0]) for p in parts]
        try:
            node = build_joined_str(tokens, self._fstring_expression)
        except FStringError as exc:
            self._error(f"f-string: {exc}", parts[0])
        except ValueError as exc:
            self._error(f"invalid string literal: {exc}", parts[0])
        # Every node inside the f-string gets the position of the whole string.
        start, end = parts[0].start, self._last.end
        for sub in ast.walk(node):
            if "lineno" in sub._attributes:
                s: Any = sub
                s.lineno, s.col_offset = start
                s.end_lineno, s.end_col_offset = end
        return node

    def _fstring_expression(self, text: str) -> ast.expr:
        """Parse the expression of one replacement field."""
        name = text.strip(" \t\n\r\f")
        if name.isascii():
            # Most fields are a name or a dotted name, such as {total} or {self.age}.
            parts = name.split(".")
            if all(p.isidentifier() and p not in _KEYWORDS for p in parts):
                node: ast.expr = _name(parts[0], _LOAD)
                for attr in parts[1:]:
                    node = _attribute(node, attr, _LOAD)
                return node
        adapter = _plain_adapter(self._lang)
        try:
            # Brackets make the lexer treat newlines in the field as plain spaces.
            tokens = OrmLexer(f"({text})", adapter).tokenize()
            inner = tokens[1:-3]  # drop "(", ")", NEWLINE and ENDMARKER
            end = inner[-1].end if inner else (1, 1)
            inner.append(tokenize.TokenInfo(NEWLINE, "", end, end, ""))
            inner.append(tokenize.TokenInfo(ENDMARKER, "", end, end, ""))
            return _Parser(inner, adapter).fstring_expression()
        except OrmError as exc:
            raise FStringError(exc.message) from exc

    def _paren_atom(self) -> ast.expr:
        start = self._advance().start
        if self._is_op(")"):
            self._advance()
            return self._at(ast.Tuple(elts=[], ctx=_LOAD), start)
        if self._is_kw("yield") or self._is_kw("yield from"):
            value = self._yield_expr()
            self._expect_op(")")
            return value
        first = self._star_named_expression()
        if self._is_kw("for") or self._is_kw("async"):
            generators = self._comprehension_clauses(first)
            self._expect_op(")")
            return self._at(ast.GeneratorExp(elt=first, generators=generators), start)
        if self._is_op(","):
            elts = [first]
            while self._accept_op(","):
                if self._is_op(")"):
                    break
                elts.append(self._star_named_expression())
            self._expect_op(")")
            return self._at(ast.Tuple(elts=elts, ctx=_LOAD), start)
        self._expect_op(")")
        if isinstance(first, ast.Starred):
            self._error("cannot use a starred expression here")
        return first

    def _list_atom(self) -> ast.expr:
        start = self._advance().start
        if self._is_op("]"):
            self._advance()
            return self._at(ast.List(elts=[], ctx=_LOAD), start)
        first = self._star_named_expression()
        if self._is_kw("for") or self._is_kw("async"):
            generators = self._comprehension_clauses(first)
            self._expect_op("]")
            return self._at(ast.ListComp(elt=first, generators=generators), start)
        elts = [first]
        while self._accept_op(","):
            if self._is_op("]"):
                break
            elts.append(self._star_named_expression())
        self._expect_op("]")
        return self._at(ast.List(elts=elts, ctx=_LOAD), start)

    def _brace_atom(self) -> ast.expr:
        start = self._advance().start
        if self._is_op("}"):
            self._advance()
            return self._at(ast.Dict(keys=[], values=[]), start)
        if self._is_op("**"):
            return self._dict_rest(start, [], [])
        first_tok = self._tok
        first = self._star_named_expression()
        if self._is_op(":") and not isinstance(first, ast.Starred):
            if isinstance(first, ast.NamedExpr) and first_tok.string != "(":
                self._error("an assignment expression as a key needs brackets")
            self._advance()
            value = self._expression()
            if self._is_kw("for") or self._is_kw("async"):
                generators = self._comprehension_clauses(first)
                self._expect_op("}")
                return self._at(
                    ast.DictComp(key=first, value=value, generators=generators), start
                )
            return self._dict_rest(start, [first], [value])
        if self._is_kw("for") or self._is_kw("async"):
            generators = self._comprehension_clauses(first)
            self._expect_op("}")
            return self._at(ast.SetComp(elt=first, generators=generators), start)
        elts = [first]
        while self._accept_op(","):
            if self._is_op("}"):
                break
            elts.append(self._star_named_expression())
        self._expect_op("}")
        return self._at(ast.Set(elts=elts), start)

    def _dict_rest(
        self, start: _PosType, keys: list[ast.expr | None], values: list[ast.expr]
    ) -> ast.expr:
        """Parse the remaining items of a dict display."""
        if keys and not self._accept_op(","):
            self._expect_op("}")
            return self._at(ast.Dict(keys=keys, values=values), start)
        while not self._is_op("}"):
            if self._accept_op("**"):
                keys.append(None)
                values.append(self._bitor_expr())
            else:
                keys.append(self._expression())
                self._expect_op(":")
                values.append(self._expression())
            if not self._accept_op(","):
                break
        self._expect_op("}")
        return self._at(ast.Dict(keys=keys, values=values), start)

    def _comprehension_clauses(self, elt: ast.expr) -> list[ast.comprehension]:
        if isinstance(elt, ast.Starred):
            self._error("iterable unpacking cannot be used in comprehension")
        clauses: list[ast.comprehension] = []
        while True:
            is_async = 0
            if self._is_kw("async"):
                self._advance()
                is_async = 1
            if not self._is_kw("for"):
                if is_async:
                    self._error("expected 'for' after 'async'")
                break
            self._advance()
            target = self._target_list()
            self._expect_kw("in")
            iter_ = self._disjunction()
            ifs: list[ast.expr] = []
            while self._accept_kw("if"):
                ifs.append(self._disjunction())
            clauses.append(
                ast.comprehension(target=target, iter=iter_, ifs=ifs, is_async=is_async)
            )
        return clauses


def _with_graphemes(node: _N, text: str | None) -> _N:
    """Attach the graphemes of ``text`` to ``node`` as ``node.graphemes``."""
    if text:
        n: Any = node
        n.graphemes = grapheme_nodes(text)
    return node


def _name(identifier: str, ctx: ast.expr_context) -> ast.Name:
    node = ast.Name(id=identifier, ctx=ctx)
    n: Any = node
    n.graphemes = grapheme_nodes(identifier)
    return node


def _attribute(value: ast.expr, attr: str, ctx: ast.expr_context) -> ast.Attribute:
    node = ast.Attribute(value=value, attr=attr, ctx=ctx)
    n: Any = node
    n.graphemes = grapheme_nodes(attr)
    return node


@functools.lru_cache(maxsize=16)
def _plain_adapter(lang: str) -> Adapter:
    """An adapter with no keywords, for text that is already translated."""
    return Adapter(lang=lang, keyword_map={}, builtin_map={}, error_messages={})


def _prefix(text: str) -> str:
    """Return the prefix letters of a string token, for example ``rb``."""
    if text[0] in "\"'":
        return ""
    return text[:1] if text[1] in "\"'" else text[:2]


class OrmParser:
    """Parse a translated token stream into a Python AST.

    Args:
        adapter: The loaded Adapter for the active language.
    """

    def __init__(self, adapter: Adapter) -> None:
        self._adapter = adapter

    def parse(self, tokens: list[tokenize.TokenInfo]) -> ast.AST:
        """Convert tokens to AST.

        Args:
            tokens: Translated token list from OrmLexer.tokenize().

        Returns:
            A valid Python AST.

        Raises:
            OrmSyntaxError: If the source has a syntax error.
        """
        hooks = self._adapter.grammar_hooks
        hook = getattr(hooks, "pre_parse", None) if hooks is not None else None
        if hook is not None:
            # A hook works on source text, so it cannot see the token list.
            # If it changes the text, the standard parser reads the new text.
            source = tokenize.untokenize(tokens)
            new_source = hook(source)
            if new_source != source:
                return self._stdlib_parse(new_source)
        parser = _Parser(tokens, self._adapter)
        try:
            with gc_paused():
                return parser.parse_module()
        except RecursionError as exc:
            # Each level of brackets or blocks uses many Python frames.
            raise OrmSyntaxError(
                code="E0010",
                message="Too many levels of nesting",
                orm_line=parser._tok.start[0],
                orm_col=parser._tok.start[1] + 1,
                lang=self._adapter.lang,
                context={"text": parser._tok.line.rstrip("\n")},
            ) from exc

    def _stdlib_parse(self, source: str) -> ast.AST:
        try:
            return ast.parse(source, filename="<orm>", type_comments=False)
        except SyntaxError as exc:
            raise OrmSyntaxError(
                code="E0010",
                message=exc.msg,
                orm_line=exc.lineno or 0,
                orm_col=exc.offset or 0,
                lang=self._adapter.lang,
                context={"text": exc.text or ""},
            ) from exc
