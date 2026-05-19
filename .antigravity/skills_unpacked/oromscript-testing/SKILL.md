---
name: oromscript-testing
description: >
  Write, run, or debug tests for the OromScript project at any layer.
  Use this skill whenever the task involves: unit tests for any core module (lexer,
  parser, semantic, codegen, errors, adapter), integration tests using the corpus
  (.orm + .py pairs), CLI integration tests (subprocess-based), performance benchmarks
  (transpile time, runtime parity), schema validation tests, coverage reports,
  pytest configuration, conftest.py fixtures, or anything under tests/ or
  adapters/*/tests/. Also use when debugging a failing test or deciding what to test
  for a new feature. This skill is the single source of truth for all testing decisions.
---

# OromScript Testing

## Test Layer Overview

```
Layer           Location                    Tool            Coverage target
─────────────────────────────────────────────────────────────────────────────
Unit            tests/test_*.py             pytest          ≥ 90% line coverage
Adapter unit    adapters/*/tests/test_*.py  pytest          100% keyword coverage
Corpus (E2E)    adapters/*/tests/corpus/    pytest          every keyword category
CLI integration tests/test_cli.py           pytest+subprocess  all commands
Performance     benchmarks/bench.py         custom          transpile < 20 ms
Schema          (run via validate-adapter)  jsonschema      all adapters
Error paths     tests/test_errors.py        pytest          every error code
```

---

## pytest Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "adapters"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "--tb=short",
    "--strict-markers",
    "-q",
]
markers = [
    "slow: marks tests as slow (deselect with -m 'not slow')",
    "corpus: marks corpus round-trip tests",
    "perf: marks performance tests",
]

[tool.coverage.run]
source = ["oromscript"]
omit = ["oromscript/cli.py"]   # CLI tested via subprocess

[tool.coverage.report]
fail_under = 90
show_missing = true
```

---

## conftest.py (shared fixtures)

```python
# tests/conftest.py
from __future__ import annotations

import pytest
from pathlib import Path
from oromscript.adapter import Adapter, AdapterRegistry

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"

@pytest.fixture(scope="session", autouse=True)
def discover_adapters() -> None:
    """Ensure all adapters are registered before any test runs."""
    AdapterRegistry.discover(ADAPTERS_DIR)

@pytest.fixture
def oromo_adapter() -> Adapter:
    return AdapterRegistry.get("afan_oromo")

@pytest.fixture
def sample_source() -> str:
    return 'agarsiisi("Akkam, Addunyaa!")'

@pytest.fixture
def sample_py() -> str:
    return 'print("Akkam, Addunyaa!")'
```

---

## Unit Tests

### tests/test_lexer.py

```python
from __future__ import annotations
import tokenize
import pytest
from oromscript.lexer import OrmLexer
from oromscript.adapter import AdapterRegistry
from oromscript.errors import OrmLexError


def test_translates_keyword(oromo_adapter):
    """'agarsiisi' should be translated to 'print'."""
    lexer = OrmLexer('agarsiisi("hello")', oromo_adapter)
    tokens = lexer.tokenize()
    names = [t.string for t in tokens if t.type == tokenize.NAME]
    assert "print" in names
    assert "agarsiisi" not in names


def test_untranslated_identifier_preserved(oromo_adapter):
    """User-defined identifier 'maqaa' must pass through unchanged."""
    lexer = OrmLexer("maqaa = 42", oromo_adapter)
    tokens = lexer.tokenize()
    names = [t.string for t in tokens if t.type == tokenize.NAME]
    assert "maqaa" in names


def test_preserves_string_contents(oromo_adapter):
    """Oromo words inside string literals must NOT be translated."""
    source = 'x = "agarsiisi fi hanga"'
    lexer = OrmLexer(source, oromo_adapter)
    tokens = lexer.tokenize()
    strings = [t.string for t in tokens if t.type == tokenize.STRING]
    assert '"agarsiisi fi hanga"' in strings


def test_lex_error_on_bad_char(oromo_adapter):
    """Invalid character should raise OrmLexError with code E0001."""
    with pytest.raises(OrmLexError) as exc_info:
        OrmLexer("\x00invalid", oromo_adapter).tokenize()
    assert exc_info.value.code == "E0001"


def test_token_immutability(oromo_adapter):
    """Original token list must not be mutated."""
    source = "yoo dhugaa:"
    lexer = OrmLexer(source, oromo_adapter)
    tokens_before = list(lexer._source)
    lexer.tokenize()
    assert list(lexer._source) == tokens_before
```

### tests/test_parser.py

```python
import ast
import pytest
from oromscript.parser import OrmParser
from oromscript.lexer import OrmLexer
from oromscript.errors import OrmSyntaxError


def test_parses_hello_world(oromo_adapter):
    source = 'agarsiisi("Akkam!")'
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    tree = OrmParser(oromo_adapter).parse(tokens)
    assert isinstance(tree, ast.AST)
    # Should contain a Call node
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert len(calls) == 1


def test_syntax_error_raises_orm_error(oromo_adapter):
    source = "yoo :"   # missing condition
    tokens = OrmLexer(source, oromo_adapter).tokenize()
    with pytest.raises(OrmSyntaxError) as exc_info:
        OrmParser(oromo_adapter).parse(tokens)
    assert exc_info.value.code == "E0010"
    assert exc_info.value.orm_line >= 1
```

### tests/test_codegen.py

```python
import ast
from oromscript.codegen import CodeGen
from oromscript import transpile


def test_hello_world_roundtrip():
    result = transpile('agarsiisi("Akkam, Addunyaa!")', lang="afan_oromo")
    assert result == 'print("Akkam, Addunyaa!")'


def test_for_loop_roundtrip():
    orm = "hanga i keessa lakkoofsa(5):\n    agarsiisi(i)"
    expected = "for i in range(5):\n    print(i)"
    assert transpile(orm) == expected


def test_class_roundtrip():
    orm = "gosa Barataa:\n    darbii"
    result = transpile(orm)
    assert "class Barataa:" in result


def test_emit_map_returns_tuple():
    result = transpile('agarsiisi("x")', emit_map=True)
    assert isinstance(result, tuple)
    assert len(result) == 2
    py_src, map_json = result
    assert 'print' in py_src
    assert '"version"' in map_json


def test_deterministic_output():
    """Same input must always produce identical output."""
    src = "hanga i keessa lakkoofsa(10):\n    agarsiisi(i * 2)"
    assert transpile(src) == transpile(src)
```

---

## Corpus Test Runner

The corpus runner auto-discovers all `.orm` + `.py` pairs in every adapter's `corpus/` folder.

```python
# tests/test_corpus.py
from __future__ import annotations

import pytest
from pathlib import Path
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
                cases.append(pytest.param(lang, orm_file, py_file, id=f"{lang}/{orm_file.stem}"))
    return cases


@pytest.mark.corpus
@pytest.mark.parametrize("lang,orm_path,py_path", collect_corpus_cases())
def test_corpus(lang: str, orm_path: Path, py_path: Path) -> None:
    """Transpiled .orm must exactly match the reference .py."""
    source = orm_path.read_text(encoding="utf-8")
    expected = py_path.read_text(encoding="utf-8").strip()
    result = transpile(source, lang=lang).strip()
    assert result == expected, (
        f"\nAdapter: {lang}\nFile: {orm_path.name}\n"
        f"--- Expected ---\n{expected}\n"
        f"--- Got ---\n{result}"
    )
```

---

## CLI Integration Tests

```python
# tests/test_cli.py
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PYTHON = sys.executable
CLI = [PYTHON, "-m", "oromscript.cli"]


def run(*args, input_text: str | None = None):
    return subprocess.run(
        [*CLI, *args],
        capture_output=True, text=True, input=input_text,
    )


def test_run_hello_world(tmp_path):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("Akkam!")', encoding="utf-8")
    result = run("run", str(f))
    assert result.returncode == 0
    assert "Akkam!" in result.stdout


def test_compile_writes_py(tmp_path):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("test")', encoding="utf-8")
    result = run("compile", str(f))
    assert result.returncode == 0
    py_out = tmp_path / "hello.py"
    assert py_out.exists()
    assert 'print("test")' in py_out.read_text()


def test_check_exits_0_on_clean(tmp_path):
    f = tmp_path / "clean.orm"
    f.write_text("x = 1", encoding="utf-8")
    result = run("check", str(f))
    assert result.returncode == 0


def test_check_exits_1_on_error(tmp_path):
    f = tmp_path / "broken.orm"
    f.write_text("yoo :", encoding="utf-8")   # bad syntax
    result = run("check", str(f))
    assert result.returncode == 1
    assert "E0010" in result.stderr


def test_validate_adapter_passes_for_oromo():
    result = run("validate-adapter", "adapters/afan_oromo/")
    assert result.returncode == 0
    assert "✓" in result.stdout
```

---

## Performance Benchmarks

```python
# benchmarks/bench.py
"""
OromScript performance benchmark.

Usage:
    python benchmarks/bench.py           # human-readable output
    python benchmarks/bench.py --ci      # fail if any stage exceeds budget
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from oromscript import transpile

BUDGET_MS = {
    "transpile_small":  20,   # < 20 ms for a ~100 line file
    "transpile_large":  100,  # < 100 ms for a ~1000 line file
}

SMALL = Path("examples/fibonacci.orm").read_text()
LARGE = SMALL * 10   # synthetic 1000-line load


def bench(name: str, fn, reps: int = 100) -> float:
    """Return mean ms over `reps` repetitions."""
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    mean = sum(times) / len(times)
    return mean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()

    results: dict[str, float] = {
        "transpile_small": bench("small", lambda: transpile(SMALL)),
        "transpile_large": bench("large", lambda: transpile(LARGE), reps=20),
    }

    print("\nOromScript Benchmark Results")
    print("=" * 40)
    failed = False
    for name, ms in results.items():
        budget = BUDGET_MS[name]
        status = "✓" if ms <= budget else "✗"
        print(f"  {status} {name:<25} {ms:6.2f} ms  (budget: {budget} ms)")
        if ms > budget:
            failed = True

    if args.ci and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

---

## Coverage Enforcement

```bash
# Run with coverage report
pytest tests/ adapters/*/tests/ --cov=oromscript --cov-report=term-missing

# Fail if below 90%
pytest tests/ --cov=oromscript --cov-fail-under=90
```

CI runs coverage on every PR. The 90% threshold is enforced via `fail_under` in `pyproject.toml`.

---

## Corpus Maintenance Guide

When adding a new Python language feature (e.g. `match`/`case`):
1. Add the keyword to `keyword_map.json` with its Oromo equivalent.
2. Create `adapters/afan_oromo/tests/corpus/NNN_match.orm` (input).
3. Run `oromscript compile adapters/afan_oromo/tests/corpus/NNN_match.orm --stdout` to generate expected output.
4. Save output as `NNN_match.py`.
5. Run `pytest -k NNN_match` to confirm the test passes.

**Never hand-edit the `.py` corpus file** — always generate it from the transpiler.
The corpus `.py` file is the ground truth of what the transpiler should produce.
