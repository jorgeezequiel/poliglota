"""Tests for glossary management and application."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from poliglota.quality.glossary import Glossary

if TYPE_CHECKING:
    pass


def test_glossary_load_json_valid(tmp_path: Path) -> None:
    """Glossary can load terms from a valid JSON file."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        json.dumps({"Hello": "Olá", "Goodbye": "Adeus"}, ensure_ascii=False),
        encoding="utf-8",
    )

    glossary = Glossary()
    glossary.load_json(glossary_file, "pt_BR")

    loaded = glossary.get_for_locale("pt_BR")
    assert loaded == {"Hello": "Olá", "Goodbye": "Adeus"}


def test_glossary_load_json_nonexistent_file() -> None:
    """Glossary raises FileNotFoundError for missing file."""
    glossary = Glossary()

    with pytest.raises(FileNotFoundError, match="not found"):
        glossary.load_json("/nonexistent/path/glossary.json", "pt_BR")


def test_glossary_load_json_invalid_json(tmp_path: Path) -> None:
    """Glossary raises ValueError for invalid JSON."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text("{invalid json}", encoding="utf-8")

    glossary = Glossary()

    with pytest.raises(ValueError, match="Invalid JSON"):
        glossary.load_json(glossary_file, "pt_BR")


def test_glossary_load_json_not_dict(tmp_path: Path) -> None:
    """Glossary raises ValueError if JSON is not a dict."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text('["not", "a", "dict"]', encoding="utf-8")

    glossary = Glossary()

    with pytest.raises(ValueError, match="must be a JSON object"):
        glossary.load_json(glossary_file, "pt_BR")


def test_glossary_load_json_non_string_key(tmp_path: Path) -> None:
    """Glossary accepts numeric keys (JSON always converts to string)."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text('{"123": "value"}', encoding="utf-8")

    glossary = Glossary()
    glossary.load_json(glossary_file, "pt_BR")

    loaded = glossary.get_for_locale("pt_BR")
    # JSON keys are always strings after parsing
    assert "123" in loaded
    assert loaded["123"] == "value"


def test_glossary_load_json_non_string_value(tmp_path: Path) -> None:
    """Glossary raises ValueError if values are not strings."""
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text('{"term": 123}', encoding="utf-8")

    glossary = Glossary()

    with pytest.raises(ValueError, match="values must be strings"):
        glossary.load_json(glossary_file, "pt_BR")


def test_glossary_load_csv_valid(tmp_path: Path) -> None:
    """Glossary can load terms from a valid CSV file."""
    glossary_file = tmp_path / "glossary.csv"
    glossary_file.write_text("Hello,Olá\nGoodbye,Adeus\n", encoding="utf-8")

    glossary = Glossary()
    glossary.load_csv(glossary_file, "pt_BR")

    loaded = glossary.get_for_locale("pt_BR")
    assert loaded == {"Hello": "Olá", "Goodbye": "Adeus"}


def test_glossary_load_csv_with_comments(tmp_path: Path) -> None:
    """Glossary ignores CSV lines starting with #."""
    glossary_file = tmp_path / "glossary.csv"
    glossary_file.write_text("# Comment\nHello,Olá\n# Another comment\nGoodbye,Adeus\n", encoding="utf-8")

    glossary = Glossary()
    glossary.load_csv(glossary_file, "pt_BR")

    loaded = glossary.get_for_locale("pt_BR")
    assert loaded == {"Hello": "Olá", "Goodbye": "Adeus"}


def test_glossary_load_csv_with_whitespace(tmp_path: Path) -> None:
    """Glossary trims whitespace from CSV terms."""
    glossary_file = tmp_path / "glossary.csv"
    glossary_file.write_text("  Hello  ,  Olá  \n", encoding="utf-8")

    glossary = Glossary()
    glossary.load_csv(glossary_file, "pt_BR")

    loaded = glossary.get_for_locale("pt_BR")
    assert loaded == {"Hello": "Olá"}


def test_glossary_load_csv_invalid_format(tmp_path: Path) -> None:
    """Glossary raises ValueError for CSV with wrong number of columns."""
    glossary_file = tmp_path / "glossary.csv"
    # Line with only one part (no comma) - will fail the validation
    glossary_file.write_text("HelloNoComma\n", encoding="utf-8")

    glossary = Glossary()

    with pytest.raises(ValueError, match="expected 2 comma-separated values"):
        glossary.load_csv(glossary_file, "pt_BR")


def test_glossary_apply_to_text_basic(tmp_path: Path) -> None:
    """Glossary applies terms to text with word boundaries."""
    glossary = Glossary()
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        json.dumps({"Hello": "Olá", "World": "Mundo"}, ensure_ascii=False),
        encoding="utf-8",
    )
    glossary.load_json(glossary_file, "pt_BR")

    result = glossary.apply_to_text("Hello World", "pt_BR")

    assert result == "Olá Mundo"


def test_glossary_apply_to_text_respects_word_boundaries(tmp_path: Path) -> None:
    """Glossary does not replace terms inside larger words."""
    glossary = Glossary()
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(json.dumps({"cat": "gato"}, ensure_ascii=False), encoding="utf-8")
    glossary.load_json(glossary_file, "pt_BR")

    result = glossary.apply_to_text("The catalog has a cat", "pt_BR")

    # "cat" inside "catalog" should NOT be replaced, but standalone "cat" should
    assert result == "The catalog has a gato"


def test_glossary_apply_to_text_case_sensitive(tmp_path: Path) -> None:
    """Glossary respects case sensitivity option."""
    glossary = Glossary()
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(json.dumps({"hello": "olá"}, ensure_ascii=False), encoding="utf-8")
    glossary.load_json(glossary_file, "pt_BR")

    result_sensitive = glossary.apply_to_text("Hello world", "pt_BR", case_sensitive=True)
    result_insensitive = glossary.apply_to_text("Hello world", "pt_BR", case_sensitive=False)

    # Case-sensitive: "Hello" (capital H) should not match "hello"
    assert result_sensitive == "Hello world"

    # Case-insensitive: "Hello" should match and be replaced
    assert result_insensitive == "olá world"


def test_glossary_apply_to_text_empty_glossary(tmp_path: Path) -> None:
    """Glossary returns original text if glossary not loaded for locale."""
    glossary = Glossary()

    result = glossary.apply_to_text("Hello World", "pt_BR")

    assert result == "Hello World"


def test_glossary_apply_to_entries_string_values(tmp_path: Path) -> None:
    """Glossary applies terms to string values in entries dict."""
    glossary = Glossary()
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        json.dumps({"Hello": "Olá", "Settings": "Configurações"}, ensure_ascii=False),
        encoding="utf-8",
    )
    glossary.load_json(glossary_file, "pt_BR")

    entries = {
        "greeting": "Hello there",
        "settings_title": "Settings",
        "count": 42,  # Non-string, should be left alone
    }

    result = glossary.apply_to_entries(entries, "pt_BR")

    assert result["greeting"] == "Olá there"
    assert result["settings_title"] == "Configurações"
    assert result["count"] == 42


def test_glossary_apply_to_entries_preserves_unaffected_keys(tmp_path: Path) -> None:
    """Glossary preserves entries without matching terms."""
    glossary = Glossary()
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(json.dumps({"Hello": "Olá"}, ensure_ascii=False), encoding="utf-8")
    glossary.load_json(glossary_file, "pt_BR")

    entries = {"greeting": "Hello", "farewell": "Goodbye"}

    result = glossary.apply_to_entries(entries, "pt_BR")

    assert result["greeting"] == "Olá"
    assert result["farewell"] == "Goodbye"


def test_glossary_multiple_locales(tmp_path: Path) -> None:
    """Glossary can store separate dictionaries for multiple locales."""
    glossary = Glossary()
    glossary_file_pt = tmp_path / "glossary_pt.json"
    glossary_file_es = tmp_path / "glossary_es.json"

    glossary_file_pt.write_text(json.dumps({"Hello": "Olá"}, ensure_ascii=False), encoding="utf-8")
    glossary_file_es.write_text(json.dumps({"Hello": "Hola"}, ensure_ascii=False), encoding="utf-8")

    glossary.load_json(glossary_file_pt, "pt_BR")
    glossary.load_json(glossary_file_es, "es_ES")

    result_pt = glossary.apply_to_text("Hello World", "pt_BR")
    result_es = glossary.apply_to_text("Hello World", "es_ES")

    assert result_pt == "Olá World"
    assert result_es == "Hola World"
