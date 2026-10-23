"""Tests for FormatRegistry and format-agnostic operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from poliglota.formats.arb import ARBFormatAdapter
from poliglota.formats.registry import FormatRegistry
from poliglota.formats.operations import validate_with_adapter, sync_with_adapter, discover_resources

if TYPE_CHECKING:
    pass


def test_format_registry_registers_and_retrieves_adapters() -> None:
    """FormatRegistry can register and retrieve adapters by name."""
    registry = FormatRegistry()
    adapter = ARBFormatAdapter()
    
    registry.register(adapter)
    
    retrieved = registry.get("arb")
    assert retrieved.name == "arb"


def test_format_registry_raises_keyerror_for_unknown_format() -> None:
    """FormatRegistry raises KeyError when retrieving an unknown format."""
    registry = FormatRegistry()
    
    with pytest.raises(KeyError, match="Format 'unknown' not registered"):
        registry.get("unknown")


def test_format_registry_lists_all_registered_formats() -> None:
    """FormatRegistry.names() returns sorted list of registered formats."""
    registry = FormatRegistry()
    registry.register(ARBFormatAdapter())
    
    names = registry.names()
    assert "arb" in names


def test_validate_with_adapter_uses_format_adapter(tmp_path: Path) -> None:
    """validate_with_adapter works with any FormatAdapter (validates via adapter)."""
    from tests.test_poliglota import write_arb
    
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"
    
    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {"@@locale": "pt_BR", "welcome": "Olá, {name}!"},
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {"@@locale": "es_ES", "welcome": "Hola, {user}!"},
    )
    
    adapter = ARBFormatAdapter()
    issues = validate_with_adapter(adapter, tmp_path, "pt_BR")
    
    assert len(issues) > 0
    assert any("placeholder" in issue.lower() for issue in issues)


def test_sync_with_adapter_uses_format_adapter(tmp_path: Path) -> None:
    """sync_with_adapter works with any FormatAdapter (copies via adapter)."""
    from tests.test_poliglota import write_arb
    from poliglota.formats.arb import load_arb
    
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "es_ES"
    
    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {"@@locale": "pt_BR", "welcome": "Olá", "goodbye": "Até logo"},
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {"@@locale": "es_ES", "welcome": "Hola"},
    )
    
    adapter = ARBFormatAdapter()
    changed = sync_with_adapter(adapter, tmp_path, "pt_BR", dry_run=False)
    
    assert changed > 0
    target_data = load_arb(target_dir / "app_core_es_ES.arb")
    assert "goodbye" in target_data
    assert target_data["goodbye"] == "Até logo"


def test_discover_resources_groups_by_locale(tmp_path: Path) -> None:
    """discover_resources groups LocalizedResource objects by locale code."""
    from tests.test_poliglota import write_arb
    
    source_dir = tmp_path / "lib" / "l10n" / "brasil"
    target_dir = tmp_path / "lib" / "l10n" / "espanha"
    
    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {"@@locale": "pt_BR", "hello": "Olá"},
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {"@@locale": "es_ES", "hello": "Hola"},
    )
    
    adapter = ARBFormatAdapter()
    by_locale = discover_resources(adapter, tmp_path)
    
    assert "pt_BR" in by_locale
    assert "es_ES" in by_locale
    assert len(by_locale["pt_BR"]) >= 1
    assert len(by_locale["es_ES"]) >= 1
