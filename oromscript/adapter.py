"""
oromscript.adapter
~~~~~~~~~~~~~~~~~~
Adapter data class and registry.

An Adapter encapsulates all language-specific data (keyword maps,
error messages, optional grammar hooks) for one local language.
"""

from __future__ import annotations

import contextlib
import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .errors import OrmAdapterError


@dataclass
class Adapter:
    lang: str
    keyword_map: dict[str, str]
    builtin_map: dict[str, str]
    error_messages: dict[str, str]
    grammar_hooks: ModuleType | None = field(default=None, repr=False)

    @classmethod
    def load(cls, adapter_dir: Path) -> Adapter:
        """Load an adapter from a directory.

        Args:
            adapter_dir: Path to the adapter folder (must contain keyword_map.json).

        Raises:
            OrmAdapterError: If keyword_map.json is missing or malformed.
        """
        kmap_path = adapter_dir / "keyword_map.json"
        if not kmap_path.exists():
            raise OrmAdapterError(
                code="E0050",
                message=f"keyword_map.json not found in {adapter_dir}",
                lang=adapter_dir.name,
            )
        raw = json.loads(kmap_path.read_text(encoding="utf-8"))
        lang = raw.get("$lang", adapter_dir.name)

        # Load optional error messages
        err_path = adapter_dir / "error_messages.json"
        error_messages: dict[str, str] = {}
        if err_path.exists():
            error_messages = json.loads(err_path.read_text(encoding="utf-8"))

        # Load optional grammar hooks module
        hooks: ModuleType | None = None
        with contextlib.suppress(ModuleNotFoundError):
            hooks = importlib.import_module(
                f"adapters.{adapter_dir.name}.grammar_hooks"
            )

        return cls(
            lang=lang,
            keyword_map=raw.get("keywords", {}),
            builtin_map=raw.get("builtins", {}),
            error_messages=error_messages,
            grammar_hooks=hooks,
        )


class AdapterRegistry:
    """Global registry of available language adapters."""

    _adapters: dict[str, Adapter] = {}

    @classmethod
    def discover(cls, adapters_dir: Path) -> None:
        """Scan adapters_dir and register all found adapters."""
        for d in adapters_dir.iterdir():
            if (
                d.is_dir()
                and (d / "keyword_map.json").exists()
                and d.name not in cls._adapters
            ):
                cls._adapters[d.name] = Adapter.load(d)

    @classmethod
    def get(cls, lang: str) -> Adapter:
        if lang not in cls._adapters:
            raise OrmAdapterError(
                code="E0051",
                message=f"No adapter found for language '{lang}'. "
                f"Available: {list(cls._adapters)}",
                lang=lang,
            )
        return cls._adapters[lang]

    @classmethod
    def list_langs(cls) -> list[str]:
        return sorted(cls._adapters.keys())
