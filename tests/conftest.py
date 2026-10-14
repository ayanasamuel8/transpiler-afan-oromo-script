from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture
def plain_adapter() -> Adapter:
    """An adapter with no keywords, so the lexer leaves every name alone."""
    return Adapter(lang="plain", keyword_map={}, builtin_map={}, error_messages={})


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests marked ``slow`` unless they are asked for with ``-m slow``."""
    if "slow" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="slow test; run it with: pytest -m slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
