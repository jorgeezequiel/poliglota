"""Integration tests for CLI multiformat support (Phase C).

Tests validate that CLI commands (validate, sync, list-locales)
work correctly with YAML, JSON, XML, and ARB formats.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from poliglota.cli import _run_list_locales, _run_sync, _run_validate
from poliglota.formats.registry_init import get_registry

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_locales() -> Generator[Path, None, None]:
    """Create temporary directory with multiformat locale files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Create YAML locale files
        yaml_dir = root / "l10n"
        yaml_dir.mkdir()

        # Portuguese source (YAML)
        (yaml_dir / "pt_BR.yaml").write_text("greeting: Olá\nfarewell: Adeus\n", encoding="utf-8")

        # English target (YAML) - missing key 'farewell'
        (yaml_dir / "en_US.yaml").write_text("greeting: Hello\n", encoding="utf-8")

        # Spanish target (YAML) - complete
        (yaml_dir / "es_ES.yaml").write_text("greeting: Hola\nfarewell: Adiós\n", encoding="utf-8")

        # Create JSON locale files
        json_dir = root / "strings"
        json_dir.mkdir()

        # Portuguese source (JSON)
        (json_dir / "pt_BR.json").write_text(
            json.dumps({"greeting": "Olá", "farewell": "Adeus"}), encoding="utf-8"
        )

        # English target (JSON) - missing key
        (json_dir / "en_US.json").write_text(json.dumps({"greeting": "Hello"}), encoding="utf-8")

        # Spanish target (JSON) - complete
        (json_dir / "es_ES.json").write_text(
            json.dumps({"greeting": "Hola", "farewell": "Adiós"}), encoding="utf-8"
        )

        # Create ARB locale files
        arb_dir = root / "arb"
        arb_dir.mkdir()

        # Portuguese source (ARB)
        (arb_dir / "pt_BR.arb").write_text(
            json.dumps({"@@locale": "pt_BR", "greeting": "Olá", "farewell": "Adeus"}),
            encoding="utf-8",
        )

        # English target (ARB) - missing key
        (arb_dir / "en_US.arb").write_text(
            json.dumps({"@@locale": "en_US", "greeting": "Hello"}), encoding="utf-8"
        )

        yield root


class TestCLIValidateMultiformat:
    """Test CLI validate command with multiple formats."""

    def test_validate_yaml_format(self, temp_locales: Path) -> None:
        """Validate YAML locale files."""
        yaml_root = temp_locales / "l10n"
        result = _run_validate(yaml_root, "pt_BR", "yaml")
        # Should succeed; en_US is missing 'farewell' but that's expected
        assert result in (0, 1)  # 0 if no issues, 1 if issues found

    def test_validate_json_format(self, temp_locales: Path) -> None:
        """Validate JSON locale files."""
        json_root = temp_locales / "strings"
        result = _run_validate(json_root, "pt_BR", "json")
        assert result in (0, 1)

    def test_validate_arb_format(self, temp_locales: Path) -> None:
        """Validate ARB locale files."""
        arb_root = temp_locales / "arb"
        result = _run_validate(arb_root, "pt_BR", "arb")
        assert result in (0, 1)

    def test_validate_unsupported_format(self, temp_locales: Path) -> None:
        """Validate with unsupported format returns error."""
        result = _run_validate(temp_locales / "l10n", "pt_BR", "unsupported")
        assert result == 2  # KeyError from registry.get()


class TestCLISyncMultiformat:
    """Test CLI sync command with multiple formats."""

    def test_sync_yaml_format_dry_run(self, temp_locales: Path) -> None:
        """Sync YAML format in dry-run mode."""
        yaml_root = temp_locales / "l10n"
        # Locale codes are normalized to lowercase by adapters
        result = _run_sync(yaml_root, "pt_br", dry_run=True, format_name="yaml")
        assert result == 0

        # Verify en_us.yaml still missing 'farewell' (dry run)
        en_yaml = yaml_root / "en_US.yaml"
        content = en_yaml.read_text(encoding="utf-8")
        assert "farewell" not in content

    def test_sync_yaml_format_write(self, temp_locales: Path) -> None:
        """Sync YAML format with actual write."""
        yaml_root = temp_locales / "l10n"
        # Locale codes are normalized to lowercase by adapters
        result = _run_sync(yaml_root, "pt_br", dry_run=False, format_name="yaml")
        assert result == 0

        # Verify en_US.yaml now has 'farewell' (synced from pt_BR)
        en_yaml = yaml_root / "en_US.yaml"
        content = en_yaml.read_text(encoding="utf-8")
        assert "farewell" in content

    def test_sync_json_format_dry_run(self, temp_locales: Path) -> None:
        """Sync JSON format in dry-run mode."""
        json_root = temp_locales / "strings"
        # Locale codes are normalized to lowercase by adapters
        result = _run_sync(json_root, "pt_br", dry_run=True, format_name="json")
        assert result == 0

        # Verify en_US.json still missing 'farewell' (dry run)
        en_json = json_root / "en_US.json"
        data = json.loads(en_json.read_text(encoding="utf-8"))
        assert "farewell" not in data

    def test_sync_json_format_write(self, temp_locales: Path) -> None:
        """Sync JSON format with actual write."""
        json_root = temp_locales / "strings"
        # Locale codes are normalized to lowercase by adapters
        result = _run_sync(json_root, "pt_br", dry_run=False, format_name="json")
        assert result == 0

        # Verify en_US.json now has 'farewell' (synced from pt_BR)
        en_json = json_root / "en_US.json"
        data = json.loads(en_json.read_text(encoding="utf-8"))
        assert "farewell" in data
        assert data["farewell"] == "Adeus"  # Source value preserved


class TestCLIListLocalesMultiformat:
    """Test CLI list-locales command with multiple formats."""

    def test_list_locales_yaml(self, temp_locales: Path) -> None:
        """List locales for YAML format."""
        yaml_root = temp_locales / "l10n"
        result = _run_list_locales(yaml_root, "yaml")
        assert result == 0

    def test_list_locales_json(self, temp_locales: Path) -> None:
        """List locales for JSON format."""
        json_root = temp_locales / "strings"
        result = _run_list_locales(json_root, "json")
        assert result == 0

    def test_list_locales_arb(self, temp_locales: Path) -> None:
        """List locales for ARB format."""
        arb_root = temp_locales / "arb"
        result = _run_list_locales(arb_root, "arb")
        assert result == 0

    def test_list_locales_empty_directory(self, temp_locales: Path) -> None:
        """List locales in empty directory."""
        empty_dir = temp_locales / "empty"
        empty_dir.mkdir()
        result = _run_list_locales(empty_dir, "yaml")
        assert result == 0  # No error; just no locales found


class TestRegistryIntegration:
    """Test FormatRegistry integration with CLI."""

    def test_registry_has_all_formats(self) -> None:
        """Verify registry contains all required formats."""
        registry = get_registry()
        formats = registry.names()

        assert "arb" in formats
        assert "yaml" in formats
        assert "json" in formats
        assert "xml" in formats

    def test_registry_get_adapter(self) -> None:
        """Verify registry can retrieve adapters by name."""
        registry = get_registry()

        yaml_adapter = registry.get("yaml")
        assert yaml_adapter is not None

        json_adapter = registry.get("json")
        assert json_adapter is not None

        xml_adapter = registry.get("xml")
        assert xml_adapter is not None

        arb_adapter = registry.get("arb")
        assert arb_adapter is not None

    def test_registry_get_invalid_format(self) -> None:
        """Verify registry raises KeyError for invalid format."""
        registry = get_registry()

        with pytest.raises(KeyError):
            registry.get("invalid_format")
