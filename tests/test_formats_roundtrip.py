"""Round-trip tests for format adapters (YAML, JSON, XML, ARB).

Validates that LocalizedDocument read/write cycles preserve structure and content.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from poliglota.core.format import LocalizedDocument
from poliglota.core.locale import Locale
from poliglota.formats.arb import ARBFormatAdapter
from poliglota.formats.json import JSONFormatAdapter
from poliglota.formats.registry_init import create_default_registry
from poliglota.formats.xml import XMLFormatAdapter
from poliglota.formats.yaml import YAMLFormatAdapter


class TestYAMLRoundTrip:
    """Test YAML adapter read/write cycle."""

    def test_yaml_flat_structure(self, tmp_path: Path) -> None:
        """YAML with flat structure survives round-trip."""
        adapter = YAMLFormatAdapter()
        
        # Create test file
        yaml_file = tmp_path / "en.yaml"
        yaml_file.write_text("greeting: Hello\nfarewell: Goodbye\n", encoding="utf-8")
        
        # Read
        doc = adapter.read(yaml_file)
        assert doc.locale is not None
        assert doc.locale.code == "en"
        assert doc.entries["greeting"] == "Hello"
        assert doc.entries["farewell"] == "Goodbye"
        
        # Write
        output_file = tmp_path / "en_out.yaml"
        adapter.write(doc, output_file)
        
        # Verify
        doc2 = adapter.read(output_file)
        assert doc2.entries == doc.entries

    def test_yaml_nested_structure(self, tmp_path: Path) -> None:
        """YAML with nested structure is flattened and reconstructed."""
        adapter = YAMLFormatAdapter()
        
        yaml_file = tmp_path / "pt_BR.yaml"
        yaml_file.write_text(
            "app:\n"
            "  title: Meu App\n"
            "  menu:\n"
            "    home: Início\n"
            "    about: Sobre\n",
            encoding="utf-8",
        )
        
        # Read
        doc = adapter.read(yaml_file)
        assert doc.locale is not None
        assert doc.locale.code == "pt_br"
        assert doc.entries["app.title"] == "Meu App"
        assert doc.entries["app.menu.home"] == "Início"
        assert doc.entries["app.menu.about"] == "Sobre"
        
        # Write and verify structure is preserved
        output_file = tmp_path / "pt_BR_out.yaml"
        adapter.write(doc, output_file)
        doc2 = adapter.read(output_file)
        assert doc2.entries == doc.entries


class TestJSONRoundTrip:
    """Test JSON adapter read/write cycle."""

    def test_json_flat_structure(self, tmp_path: Path) -> None:
        """JSON with flat structure survives round-trip."""
        adapter = JSONFormatAdapter()
        
        json_file = tmp_path / "en.json"
        json_file.write_text(
            json.dumps({"greeting": "Hello", "farewell": "Goodbye"}, ensure_ascii=False),
            encoding="utf-8",
        )
        
        # Read
        doc = adapter.read(json_file)
        assert doc.locale is not None
        assert doc.locale.code == "en"
        assert doc.entries["greeting"] == "Hello"
        assert doc.entries["farewell"] == "Goodbye"
        
        # Write
        output_file = tmp_path / "en_out.json"
        adapter.write(doc, output_file)
        
        # Verify
        doc2 = adapter.read(output_file)
        assert doc2.entries == doc.entries

    def test_json_nested_structure(self, tmp_path: Path) -> None:
        """JSON with nested structure is flattened and reconstructed."""
        adapter = JSONFormatAdapter()
        
        json_file = tmp_path / "es.json"
        data = {
            "app": {
                "title": "Mi Aplicación",
                "menu": {
                    "home": "Inicio",
                    "about": "Acerca de",
                },
            }
        }
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        
        # Read
        doc = adapter.read(json_file)
        assert doc.locale is not None
        assert doc.locale.code == "es"
        assert doc.entries["app.title"] == "Mi Aplicación"
        assert doc.entries["app.menu.home"] == "Inicio"
        
        # Write and verify
        output_file = tmp_path / "es_out.json"
        adapter.write(doc, output_file)
        doc2 = adapter.read(output_file)
        assert doc2.entries == doc.entries


class TestXMLRoundTrip:
    """Test XML adapter read/write cycle."""

    def test_xml_simple_structure(self, tmp_path: Path) -> None:
        """XML with simple structure survives round-trip."""
        adapter = XMLFormatAdapter()
        
        xml_file = tmp_path / "strings_en.xml"
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<strings>
  <greeting>Hello</greeting>
  <farewell>Goodbye</farewell>
</strings>"""
        xml_file.write_text(xml_content, encoding="utf-8")
        
        # Read
        doc = adapter.read(xml_file)
        assert doc.locale is not None
        assert doc.locale.code == "en"
        assert "strings.greeting" in doc.entries
        assert "strings.farewell" in doc.entries
        
        # Write
        output_file = tmp_path / "strings_en_out.xml"
        adapter.write(doc, output_file)
        
        # Verify
        doc2 = adapter.read(output_file)
        assert set(doc2.entries.keys()) == set(doc.entries.keys())

    def test_xml_nested_structure(self, tmp_path: Path) -> None:
        """XML with nested structure is preserved."""
        adapter = XMLFormatAdapter()
        
        xml_file = tmp_path / "strings_pt_BR.xml"
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<resources>
  <app>
    <title>Meu App</title>
    <menu>
      <home>Início</home>
      <about>Sobre</about>
    </menu>
  </app>
</resources>"""
        xml_file.write_text(xml_content, encoding="utf-8")
        
        # Read
        doc = adapter.read(xml_file)
        assert doc.locale is not None
        assert doc.locale.code == "pt_br"
        
        # Write and verify
        output_file = tmp_path / "strings_pt_BR_out.xml"
        adapter.write(doc, output_file)
        doc2 = adapter.read(output_file)
        assert set(doc2.entries.keys()) == set(doc.entries.keys())


class TestRegistryIntegration:
    """Test FormatRegistry discovery and adapter registration."""

    def test_registry_has_all_adapters(self) -> None:
        """Default registry contains all format adapters."""
        registry = create_default_registry()
        
        assert "yaml" in registry.names()
        assert "json" in registry.names()
        assert "xml" in registry.names()
        assert "arb" in registry.names()

    def test_registry_adapter_retrieval(self) -> None:
        """Registry can retrieve adapters by name."""
        registry = create_default_registry()
        
        yaml_adapter = registry.get("yaml")
        assert yaml_adapter.name == "yaml"
        
        json_adapter = registry.get("json")
        assert json_adapter.name == "json"
        
        xml_adapter = registry.get("xml")
        assert xml_adapter.name == "xml"

    def test_registry_missing_format_raises(self) -> None:
        """Registry raises KeyError for unknown formats."""
        registry = create_default_registry()
        
        with pytest.raises(KeyError):
            registry.get("unknown_format")

    def test_discover_mixed_formats(self, tmp_path: Path) -> None:
        """Registry-based discovery works for mixed format types."""
        # Create test files
        (tmp_path / "en.yaml").write_text("greeting: Hello\n", encoding="utf-8")
        (tmp_path / "en.json").write_text(json.dumps({"farewell": "Goodbye"}), encoding="utf-8")
        
        registry = create_default_registry()
        
        yaml_resources = registry.get("yaml").discover(tmp_path)
        json_resources = registry.get("json").discover(tmp_path)
        
        assert len(yaml_resources) > 0
        assert len(json_resources) > 0
        assert yaml_resources[0].locale.code == "en"
        assert json_resources[0].locale.code == "en"
