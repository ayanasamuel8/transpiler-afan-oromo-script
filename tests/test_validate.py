import json
import pytest
from click.testing import CliRunner
from oromscript.cli import main
import oromscript.validate

@pytest.fixture
def runner():
    return CliRunner()

def test_validate_adapter_missing_kmap(tmp_path, runner):
    adapter = tmp_path / "bad_adapter"
    adapter.mkdir()
    result = runner.invoke(main, ["validate-adapter", str(adapter)])
    assert result.exit_code == 1
    assert "E0050" in result.output

def test_validate_adapter_duplicate(tmp_path, runner):
    adapter = tmp_path / "bad_adapter"
    adapter.mkdir()
    (adapter / "keyword_map.json").write_text(json.dumps({
        "$lang": "bad", "$version": "1.0",
        "keywords": {"k1": "dup", "k2": "dup"},
        "builtins": {}
    }))
    result = runner.invoke(main, ["validate-adapter", str(adapter)])
    assert result.exit_code == 1
    assert "E0052" in result.output

def test_validate_adapter_bad_json(tmp_path, runner):
    adapter = tmp_path / "bad_adapter"
    adapter.mkdir()
    (adapter / "keyword_map.json").write_text("{bad_json")
    result = runner.invoke(main, ["validate-adapter", str(adapter)])
    assert result.exit_code == 1
    assert "E0052" in result.output

def test_validate_adapter_no_schema(tmp_path, runner, monkeypatch):
    monkeypatch.setattr(oromscript.validate, "__file__", "/tmp/nonexistent")
    result = runner.invoke(main, ["validate-adapter", "adapters/afan_oromo"])
    assert result.exit_code == 0
