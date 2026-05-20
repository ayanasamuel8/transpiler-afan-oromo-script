import pytest
from pathlib import Path
from oromscript.adapter import AdapterRegistry, Adapter
from oromscript.errors import OrmAdapterError

def test_adapter_load_missing_kmap(tmp_path):
    with pytest.raises(OrmAdapterError) as exc:
        Adapter.load(tmp_path)
    assert exc.value.code == "E0050"

def test_adapter_registry_get_missing():
    with pytest.raises(OrmAdapterError) as exc:
        AdapterRegistry.get("nonexistent_lang")
    assert exc.value.code == "E0051"
    assert isinstance(AdapterRegistry.list_langs(), list)
