from __future__ import annotations

import ast
from pathlib import Path

import pytest

from oromscript import transpile

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"


def collect_corpus_cases():
    """Yield (lang, orm_path, py_path) for every corpus pair."""
    cases = []
    for adapter_dir in ADAPTERS_DIR.iterdir():
        corpus_dir = adapter_dir / "tests" / "corpus"
        if not corpus_dir.exists():
            continue
        lang = adapter_dir.name
        for orm_file in sorted(corpus_dir.glob("*.orm")):
            py_file = orm_file.with_suffix(".py")
            if py_file.exists():
                cases.append(
                    pytest.param(lang, orm_file, py_file, id=f"{lang}/{orm_file.stem}")
                )
    return cases


@pytest.mark.corpus
@pytest.mark.parametrize("lang,orm_path,py_path", collect_corpus_cases())
def test_corpus(lang: str, orm_path: Path, py_path: Path) -> None:
    """Transpiled .orm must match the AST of the reference .py."""
    source = orm_path.read_text(encoding="utf-8")
    expected = py_path.read_text(encoding="utf-8").strip()
    result = transpile(source, lang=lang).strip()

    expected_ast = ast.dump(ast.parse(expected))
    result_ast = ast.dump(ast.parse(result))

    assert result_ast == expected_ast, (
        f"\nAdapter: {lang}\nFile: {orm_path.name}\n"
        f"--- Expected ---\n{expected}\n"
        f"--- Got ---\n{result}"
    )
