from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from poliglota.formats.arb import load_arb
from poliglota.translation_review import TranslationReviewSession

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_review_session_persists_edits_without_overwriting_source_and_exports(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "app_home_en_US.arb"
    source.write_text(
        json.dumps(
            {
                "@@locale": "en_US",
                "hello": "Hello {name}",
                "@hello": {"description": "Greeting"},
            }
        ),
        encoding="utf-8",
    )
    translated = root / ".poliglota_translated" / "app_home_es_ES.arb"
    translated.parent.mkdir()
    translated.write_text(
        json.dumps(
            {
                "@@locale": "es_ES",
                "hello": "Hola {name}",
                "@hello": {"description": "Greeting"},
            }
        ),
        encoding="utf-8",
    )
    source_bytes = source.read_bytes()
    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert session.pending_count == 1
    assert session.items[0].context == "Greeting"

    session.save(session.items[0].file, "hello", "Saludos {name}", reviewed=True)
    assert session.pending_count == 0
    assert source.read_bytes() == source_bytes

    resumed = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    assert resumed.items[0].value == "Saludos {name}"
    assert resumed.items[0].reviewed is True
    with pytest.raises(ValueError, match="Placeholder"):
        resumed.save(resumed.items[0].file, "hello", "Saludos", reviewed=True)

    exported = resumed.export(tmp_path / "exported")
    payload = load_arb(exported / "app_home_es_ES.arb")
    assert payload["hello"] == "Saludos {name}"
    assert payload["@hello"] == {"description": "Greeting"}
    with pytest.raises(FileExistsError):
        resumed.export(exported)


@pytest.mark.unit
def test_android_review_export_keeps_nontranslatable_resources_and_format_placeholders(
    tmp_path: Path,
) -> None:
    root = tmp_path / "android"
    source_dir = root / "app" / "src" / "main" / "res" / "values-pt-rBR"
    source_dir.mkdir(parents=True)
    source = source_dir / "strings.xml"
    source.write_text(
        '<resources><string name="count">%1$s itens</string>'
        '<string name="package" translatable="false">Poliglota</string></resources>',
        encoding="utf-8",
    )
    target = (
        root
        / ".poliglota_translated"
        / "app"
        / "src"
        / "main"
        / "res"
        / "values-es-rES"
        / "strings.xml"
    )
    target.parent.mkdir(parents=True)
    target.write_text(
        '<resources><string name="count">%1$s elementos</string>'
        '<string name="package" translatable="false">Poliglota</string></resources>',
        encoding="utf-8",
    )
    session = TranslationReviewSession(root, "xml", "pt_BR", "es_ES")
    assert [item.key for item in session.items] == ["count"]
    session.save(session.items[0].file, "count", "%1$s elementos", reviewed=True)
    exported = session.export(tmp_path / "android-export")
    xml = (exported / "app" / "src" / "main" / "res" / "values-es-rES" / "strings.xml").read_text(
        encoding="utf-8"
    )
    assert 'name="count"' in xml
    assert "%1$s elementos" in xml
    assert 'name="package" translatable="false"' in xml


@pytest.mark.unit
def test_export_preliminary_files_without_saved_review(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "app_home_en_US.arb"
    source.write_text('{"@@locale":"en_US","hello":"Hello"}', encoding="utf-8")
    generated = root / ".poliglota_translated" / "app_home_es_ES.arb"
    generated.parent.mkdir()
    generated.write_text('{"@@locale":"es_ES","hello":"Hola"}', encoding="utf-8")

    session = TranslationReviewSession(root, "arb", "en_US", "es_ES")
    exported = session.export(tmp_path / "exported")

    assert (exported / generated.name).read_text(encoding="utf-8") == generated.read_text(
        encoding="utf-8"
    )
    assert source.read_text(encoding="utf-8") == '{"@@locale":"en_US","hello":"Hello"}'
