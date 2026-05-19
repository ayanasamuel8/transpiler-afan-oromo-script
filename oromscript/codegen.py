"""
oromscript.codegen
~~~~~~~~~~~~~~~~~~
Generates Python source from an annotated AST using ast.unparse().

This is the fourth (and final source-emitting) stage of the pipeline.
"""
from __future__ import annotations

import ast
import json

from .semantic import SourceMap


class CodeGen:
    """Generate Python source code from an AST."""

    def generate(
        self,
        tree: ast.AST,
        source_map: SourceMap | None = None,
    ) -> tuple[str, str | None]:
        """Generate Python source and optionally a source-map JSON.

        Args:
            tree: Annotated AST from SemanticAnalyser.
            source_map: Optional line mapping (orm_line → py_line).

        Returns:
            (py_source, map_json_or_None)
        """
        py_source = ast.unparse(tree)
        # Normalise: re-parse and re-unparse for deterministic whitespace
        py_source = ast.unparse(ast.parse(py_source))

        map_json: str | None = None
        if source_map is not None:
            map_json = json.dumps(
                {"version": 1, "mappings": source_map},
                ensure_ascii=False,
                indent=2,
            )
        return py_source, map_json
