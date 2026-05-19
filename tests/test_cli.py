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
