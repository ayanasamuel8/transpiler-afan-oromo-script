from __future__ import annotations

import sys
import pytest
from click.testing import CliRunner
from oromscript.cli import main

@pytest.fixture
def runner():
    return CliRunner()

def test_run_hello_world(tmp_path, runner):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("Akkam!")', encoding="utf-8")
    result = runner.invoke(main, ["run", str(f)])
    assert result.exit_code == 0
    assert "Akkam!" in result.output

def test_compile_writes_py(tmp_path, runner):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("test")', encoding="utf-8")
    result = runner.invoke(main, ["compile", str(f)])
    assert result.exit_code == 0
    py_out = tmp_path / "hello.py"
    assert py_out.exists()
    assert "print('test')" in py_out.read_text()

def test_check_exits_0_on_clean(tmp_path, runner):
    f = tmp_path / "clean.orm"
    f.write_text("x = 1", encoding="utf-8")
    result = runner.invoke(main, ["check", str(f)])
    assert result.exit_code == 0

def test_check_exits_1_on_error(tmp_path, runner):
    f = tmp_path / "broken.orm"
    f.write_text("yoo :", encoding="utf-8")   # bad syntax
    result = runner.invoke(main, ["check", str(f)])
    assert result.exit_code == 1
    assert "E0010" in result.output

def test_validate_adapter_passes_for_oromo(runner):
    result = runner.invoke(main, ["validate-adapter", "adapters/afan_oromo"])
    assert result.exit_code == 0
    assert "✓" in result.output

def test_run_error(tmp_path, runner):
    f = tmp_path / "err.orm"
    f.write_text('agarsiisi("', encoding="utf-8") # syntax error
    result = runner.invoke(main, ["run", str(f)])
    assert result.exit_code == 1
    assert "E0001" in result.output  # Lexing error is E0001

def test_compile_error(tmp_path, runner):
    f = tmp_path / "err.orm"
    f.write_text('agarsiisi("', encoding="utf-8")
    result = runner.invoke(main, ["compile", str(f)])
    assert result.exit_code == 1
    assert "E0001" in result.output

def test_compile_stdout(tmp_path, runner):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("test")', encoding="utf-8")
    result = runner.invoke(main, ["compile", "--stdout", str(f)])
    assert result.exit_code == 0
    assert "print('test')" in result.output

def test_compile_map(tmp_path, runner):
    f = tmp_path / "hello.orm"
    f.write_text('agarsiisi("test")', encoding="utf-8")
    result = runner.invoke(main, ["compile", "--map", str(f)])
    assert result.exit_code == 0
    assert (tmp_path / "hello.orm.map").exists()

def test_repl(runner):
    result = runner.invoke(main, ["repl"], input="agarsiisi('hi')\n")
    assert result.exit_code == 0

def test_repl_error(runner):
    result = runner.invoke(main, ["repl"], input="yoo :\n")
    assert result.exit_code == 0

def test_new_lang(tmp_path, runner, monkeypatch):
    from oromscript import cli
    monkeypatch.setattr(cli, "ADAPTERS_DIR", tmp_path)
    result = runner.invoke(main, ["new-lang", "testlang"])
    assert result.exit_code == 0
    assert (tmp_path / "testlang" / "keyword_map.json").exists()
