"""Tests for the ARB format adapter implementing the core contract."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from poliglota.core.format import LocalizedDocument
from poliglota.core.locale import Locale
from poliglota.formats.arb import ARBFormatAdapter, discover_arb_files, validate_placeholders

if TYPE_CHECKING:
    from pathlib import Path


def _write_arb(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_adapter_exposes_name_and_discovers_resources(tmp_path: Path) -> None:
    _write_arb(
        tmp_path / "lib" / "l10n" / "brasil-pt_BR" / "app_core_pt_BR.arb",
        {"@@locale": "pt_BR", "title": "Olá"},
    )

    adapter = ARBFormatAdapter()
    resources = adapter.discover(tmp_path)

    assert adapter.name == "arb"
    assert len(resources) == 1
    resource = resources[0]
    assert resource.format == "arb"
    assert resource.locale.code == "pt_BR"
    assert resource.attributes["module"] == "core"


def test_adapter_read_splits_entries_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "app_core_en.arb"
    _write_arb(
        path,
        {"@@locale": "en", "title": "Hello", "@title": {"description": "screen title"}},
    )

    document = ARBFormatAdapter().read(path)

    assert document.locale is not None
    assert document.locale.code == "en"
    assert document.entries == {"title": "Hello"}
    assert document.metadata == {"@@locale": "en", "@title": {"description": "screen title"}}


def test_adapter_write_roundtrip_preserves_content(tmp_path: Path) -> None:
    source = tmp_path / "app_core_en.arb"
    _write_arb(source, {"@@locale": "en", "title": "Hello", "@title": {"description": "t"}})

    adapter = ARBFormatAdapter()
    destination = tmp_path / "out" / "app_core_pt_BR.arb"
    adapter.write(adapter.read(source), destination)

    assert _load(destination) == _load(source)


def test_adapter_write_adds_missing_locale_header(tmp_path: Path) -> None:
    destination = tmp_path / "app_core_fr.arb"

    ARBFormatAdapter().write(
        LocalizedDocument(locale=Locale("fr"), entries={"title": "Bonjour"}),
        destination,
    )

    assert _load(destination)["@@locale"] == "fr"


def test_adapter_discovery_matches_legacy_discovery(tmp_path: Path) -> None:
    for locale, module in (("pt_BR", "core"), ("es_ES", "core"), ("ja_JP", "settings")):
        _write_arb(
            tmp_path / "l10n" / locale / f"app_{module}_{locale}.arb",
            {"@@locale": locale, "k": "v"},
        )

    adapter_resources = [
        (r.path, r.locale.code, r.attributes["module"])
        for r in ARBFormatAdapter().discover(tmp_path)
    ]
    legacy_files = [(f.path, f.locale, f.module) for f in discover_arb_files(tmp_path)]

    assert adapter_resources == legacy_files


@pytest.mark.parametrize(
    "source_data,target_data,expected_issues",
    [
        # Multiple placeholders in same string
        (
            {"msg": "Hello {first} {last}"},
            {"msg": "Hola {first}"},
            ["placeholder mismatch for 'msg' -> source=['first', 'last'] target=['first']"],
        ),
        # Valid match (both have same placeholders)
        (
            {"msg": "Hi {name}"},
            {"msg": "Hola {name}"},
            [],
        ),
        # Source has placeholder, target missing
        (
            {"greeting": "Hello {user}!"},
            {"greeting": "Hola!"},
            ["placeholder mismatch for 'greeting' -> source=['user'] target=[]"],
        ),
        # Metadata keys should be ignored (start with @)
        (
            {"@description": "This has {var}"},
            {"@description": "Esto tiene {var}"},
            [],
        ),
        # Key missing in target (should be skipped)
        (
            {"msg": "Hello {name}"},
            {},
            [],
        ),
        # Empty source/target values
        (
            {"msg": ""},
            {"msg": ""},
            [],
        ),
    ],
)
def test_validate_placeholders_edge_cases(
    source_data: dict[str, object],
    target_data: dict[str, object],
    expected_issues: list[str],
) -> None:
    """Test placeholder validation with edge cases."""
    issues = validate_placeholders(source_data, target_data)
    assert issues == expected_issues
