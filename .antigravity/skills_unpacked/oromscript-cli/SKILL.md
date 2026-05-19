---
name: oromscript-cli
description: >
  Build or modify the OromScript command-line interface (CLI) and REPL.
  Use this skill whenever the task involves: implementing or extending CLI commands
  (run, compile, check, repl, new-lang, validate-adapter), the Click application
  structure in oromscript/cli.py, the interactive REPL loop, caching logic
  (transpile-time .pyc cache), the VS Code syntax highlighting extension under
  vscode-extension/, the pyproject.toml entry point, the Makefile dev shortcuts,
  or any user-facing output formatting (rich, plain text, error display in terminal).
  Also use when writing CLI integration tests or reviewing oromscript/cli.py.
---

# OromScript CLI & REPL

The CLI is built with **Click** (the only runtime dependency outside stdlib).
It is the entry point for end users. The library API (`transpile()`/`execute()`) and
the CLI are separate — the CLI calls the library, it does not reimplement pipeline logic.

---

## Entry Point (pyproject.toml)

```toml
[project.scripts]
oromscript = "oromscript.cli:main"
```

After `pip install -e .`, users run `oromscript <command>`.

---

## Command Reference

### `oromscript run <file.orm>`

Transpile and execute an `.orm` file.

```
oromscript run hello.orm
oromscript run hello.orm --lang amharic
oromscript run hello.orm --strict          # enable strict name checking
oromscript run hello.orm --no-cache        # skip .pyc cache
```

**Algorithm:**
1. Check cache: if `__pycache__/<stem>.<lang>.cpython-<ver>.pyc` exists and its mtime ≥ `file.orm` mtime → exec the `.pyc` directly (skip transpile).
2. Otherwise: read `.orm` → `transpile()` → `compile()` → write `.pyc` → `exec()`.

**Cache path formula:**
```python
import sys
cache_name = f"{stem}.{lang}.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
cache_path = file.parent / "__pycache__" / cache_name
```

### `oromscript compile <file.orm>`

Transpile to `.py` (and optionally `.orm.map`). Does NOT execute.

```
oromscript compile hello.orm               # writes hello.py
oromscript compile hello.orm --map         # writes hello.py + hello.orm.map
oromscript compile hello.orm -o out.py     # custom output path
oromscript compile hello.orm --stdout      # print to stdout, no file written
```

### `oromscript check <file.orm>`

Lint-only: transpile and report errors, but produce no output files and do not execute.
Exit code 0 = clean, 1 = errors found.

```
oromscript check hello.orm
oromscript check hello.orm --strict
```

### `oromscript repl`

Start an interactive Afan Oromo Python REPL.

```
oromscript repl
oromscript repl --lang amharic
```

**REPL behaviour:**
- Prompt: `orm> ` (primary), `...  ` (continuation for multi-line)
- Each line (or block) is transpiled and `exec()`-ed in a persistent namespace.
- Errors are displayed localised and the REPL continues (no crash).
- Multi-line: detect incomplete input via `compile(..., 'single')` raising `SyntaxError` with `msg == "unexpected EOF"`.
- `Ctrl+D` or `quit()` / `ba'i()` exits.
- History: use `readline` if available (stdlib, no extra dep).

```python
# Minimal REPL loop skeleton
import code, readline  # noqa: F401 (readline import activates history)

class OrmConsole(code.InteractiveConsole):
    def __init__(self, lang: str) -> None:
        super().__init__()
        self._lang = lang

    def runsource(self, source: str, filename: str = "<input>", symbol: str = "single") -> bool:
        try:
            py_src = transpile(source, lang=self._lang)
        except OrmError as e:
            print(str(e), file=sys.stderr)
            return False
        return super().runsource(py_src, filename, symbol)
```

### `oromscript new-lang <lang_name>`

Scaffold a new adapter directory.

```
oromscript new-lang amharic
# Creates: adapters/amharic/ with template files
```

Scaffold contents:
- `keyword_map.json` — all 35 Python keywords + 20 builtins with empty-string values.
- `error_messages.json` — all E00xx codes with empty-string values.
- `grammar_hooks.py` — no-op stub with all supported hook signatures.
- `tests/__init__.py`
- `tests/test_keywords.py` — parametrized test stub.
- `tests/corpus/` — empty directory.

After scaffolding, print:
```
✓ Adapter scaffolded at adapters/amharic/
Next steps:
  1. Fill adapters/amharic/keyword_map.json with Amharic keywords
  2. Fill adapters/amharic/error_messages.json with Amharic error messages
  3. Add corpus tests in adapters/amharic/tests/corpus/
  4. Run: oromscript validate-adapter adapters/amharic/
  5. Run: pytest adapters/amharic/tests/ -v
```

### `oromscript validate-adapter <path> [<path> ...]`

Validate one or more adapter directories against the JSON schema.

```
oromscript validate-adapter adapters/afan_oromo/
oromscript validate-adapter adapters/*/        # glob — CI usage
```

Exit code 0 = all valid, 1 = any error.
Output format (one line per adapter):
```
✓ afan_oromo  (47 keywords, 22 builtins)
✗ amharic     E0052: missing required keyword 'yield'
```

---

## CLI Implementation Skeleton (cli.py)

```python
"""
oromscript.cli
~~~~~~~~~~~~~~
Click-based command-line interface for OromScript.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from . import execute, transpile
from .adapter import AdapterRegistry
from .errors import OrmError

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"


@click.group()
@click.version_option()
def main() -> None:
    """OromScript — Write Python in your local language."""


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--lang", default="afan_oromo", show_default=True)
@click.option("--strict", is_flag=True)
@click.option("--no-cache", is_flag=True)
def run(file: Path, lang: str, strict: bool, no_cache: bool) -> None:
    """Transpile and execute FILE."""
    source = file.read_text(encoding="utf-8")
    try:
        execute(source, lang=lang)
    except OrmError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--lang", default="afan_oromo", show_default=True)
@click.option("--map", "emit_map", is_flag=True)
@click.option("-o", "--output", type=click.Path(path_type=Path))
@click.option("--stdout", is_flag=True)
def compile(file: Path, lang: str, emit_map: bool, output: Path | None, stdout: bool) -> None:
    """Transpile FILE to Python source."""
    source = file.read_text(encoding="utf-8")
    try:
        result = transpile(source, lang=lang, emit_map=emit_map)
    except OrmError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    py_src, map_json = (result if emit_map else (result, None))  # type: ignore

    if stdout:
        click.echo(py_src)
        return
    out_path = output or file.with_suffix(".py")
    out_path.write_text(py_src, encoding="utf-8")
    click.echo(f"✓ Written: {out_path}")
    if map_json and emit_map:
        map_path = file.with_suffix(".orm.map")
        map_path.write_text(map_json, encoding="utf-8")
        click.echo(f"✓ Written: {map_path}")


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--lang", default="afan_oromo", show_default=True)
@click.option("--strict", is_flag=True)
def check(file: Path, lang: str, strict: bool) -> None:
    """Lint FILE without producing output."""
    source = file.read_text(encoding="utf-8")
    try:
        transpile(source, lang=lang, strict=strict)
        click.echo(f"✓ {file} — no errors")
    except OrmError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@main.command()
@click.option("--lang", default="afan_oromo", show_default=True)
def repl(lang: str) -> None:
    """Start an interactive OromScript REPL."""
    from .repl import OrmConsole
    OrmConsole(lang=lang).interact(banner=f"OromScript REPL ({lang}) — Ctrl+D to exit")


@main.command("new-lang")
@click.argument("lang_name")
def new_lang(lang_name: str) -> None:
    """Scaffold a new language adapter directory."""
    from .scaffold import scaffold_adapter
    scaffold_adapter(lang_name, ADAPTERS_DIR)


@main.command("validate-adapter")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
def validate_adapter(paths: tuple[Path, ...]) -> None:
    """Validate adapter directories against the JSON schema."""
    from .validate import validate_adapters
    ok = validate_adapters(list(paths))
    sys.exit(0 if ok else 1)
```

---

## VS Code Extension

Located at `vscode-extension/`. Provides syntax highlighting for `.orm` files.

```
vscode-extension/
├── package.json                    # Extension manifest
├── syntaxes/
│   └── afan_oromo.tmLanguage.json  # TextMate grammar
└── README.md
```

### package.json (key fields)

```json
{
  "name": "oromscript",
  "displayName": "OromScript",
  "contributes": {
    "languages": [{
      "id": "afan-oromo",
      "aliases": ["Afan Oromo", "OrmScript"],
      "extensions": [".orm"],
      "configuration": "./language-configuration.json"
    }],
    "grammars": [{
      "language": "afan-oromo",
      "scopeName": "source.afan-oromo",
      "path": "./syntaxes/afan_oromo.tmLanguage.json"
    }]
  }
}
```

### tmLanguage Grammar Strategy

- Base scope: `source.afan-oromo`
- Include Python's TextMate grammar patterns, then override the `keyword.control` and `keyword.other` patterns to match Afan Oromo keywords.
- String and number patterns are identical to Python — reuse directly.
- Auto-generated from `keyword_map.json` using `scripts/gen_tmlanguage.py`.

```bash
# Regenerate syntax highlighting grammar from keyword_map.json
python scripts/gen_tmlanguage.py adapters/afan_oromo/keyword_map.json \
    > vscode-extension/syntaxes/afan_oromo.tmLanguage.json
```

---

## Makefile Shortcuts

```makefile
.PHONY: install test lint format check-all

install:
	pip install -e ".[dev]"

test:
	pytest tests/ adapters/*/tests/ -v --tb=short

lint:
	ruff check oromscript/ adapters/
	mypy oromscript/

format:
	black oromscript/ adapters/ tests/
	ruff check --fix oromscript/ adapters/

check-all: lint test
	python -m oromscript.cli validate-adapter adapters/*/
	python benchmarks/bench.py --ci

repl:
	oromscript repl

bench:
	python benchmarks/bench.py
```
