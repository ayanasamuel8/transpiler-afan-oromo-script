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
