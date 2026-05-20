"""
oromscript.semantic
~~~~~~~~~~~~~~~~~~~
Single-pass AST visitor that builds a symbol table and annotates nodes
with original source-map information.

This is the third stage of the OromScript transpile pipeline.
"""

from __future__ import annotations

import ast
from collections import ChainMap

# Type alias: generated-py-line → orm-line
SourceMap = dict[int, int]


class _Scope(ChainMap):
    """Nested symbol table using ChainMap for O(1) push/pop."""


class SemanticAnalyser(ast.NodeVisitor):
    """Analyse and annotate an AST.

    Args:
        source_lines: Original .orm source split by line (for error context).
        strict: If True, raise OrmNameError on undefined name references.
    """

    def __init__(self, source_lines: list[str], strict: bool = False) -> None:
        self._lines = source_lines
        self._strict = strict
        self._scope: _Scope = _Scope()
        self._orm_line_map: dict[int, int] = {}  # ast node id → orm_line

    def analyse(self, tree: ast.AST) -> tuple[ast.AST, SourceMap]:
        """Run analysis pass.

        Returns:
            (annotated_tree, source_map) where source_map maps
            each AST node's lineno to the original orm line number.
        """
        self.visit(tree)
        return tree, self._orm_line_map

    # ── Visitors ──────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope[node.name] = "function"
        self._scope = self._scope.new_child()
        for arg in node.args.args:
            self._scope[arg.arg] = "arg"
        self.generic_visit(node)
        self._scope = self._scope.parents

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope[node.name] = "class"
        self._scope = self._scope.new_child()
        self.generic_visit(node)
        self._scope = self._scope.parents

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._scope[target.id] = "var"
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if (
            self._strict
            and isinstance(node.ctx, ast.Load)
            and node.id not in self._scope
            and node.id not in dir(__builtins__)
        ):
            from .errors import OrmNameError

            raise OrmNameError(
                code="E0020",
                message=f"Name '{node.id}' is not defined",
                orm_line=getattr(node, "lineno", 0),
                orm_col=getattr(node, "col_offset", 0),
                lang="",
                context={"name": node.id},
            )
