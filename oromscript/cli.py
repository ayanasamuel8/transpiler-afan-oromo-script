"""
oromscript.cli
~~~~~~~~~~~~~~
Click-based command-line interface for OromScript.
"""
from __future__ import annotations

import sys
from pathlib import Path
import code

import click

from . import execute, transpile
from .adapter import AdapterRegistry
from .errors import OrmError

ADAPTERS_DIR = Path(__file__).parent.parent / "adapters"

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
    try:
        import readline  # noqa: F401
    except ImportError:
        pass
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
