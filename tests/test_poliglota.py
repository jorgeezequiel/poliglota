from __future__ import annotations

import json
from typing import TYPE_CHECKING

from poliglota.cli import main
from poliglota.syncer import sync_locale_files
from poliglota.validator import validate_root

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def write_arb(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_validate_root_detects_missing_keys_and_placeholder_mismatch(tmp_path: Path) -> None:
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"

    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {
            "@@locale": "pt_BR",
            "welcome": "Olá, {name}!",
            "count": "Você tem {count} itens",
            "settings": "Configurações",
        },
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {
            "@@locale": "es_ES",
            "welcome": "Hola, {user}!",
            "count": "Tienes {quantity} artículos",
        },
    )

    issues = validate_root(tmp_path, "pt_BR")

    assert any("missing keys" in issue for issue in issues)
    assert any("placeholder mismatch" in issue for issue in issues)


def test_sync_locale_files_copies_missing_keys(tmp_path: Path) -> None:
    source_dir = tmp_path / "lib" / "l10n" / "americas" / "sul" / "brasil-pt_BR"
    target_dir = tmp_path / "lib" / "l10n" / "europa" / "es_ES"

    write_arb(
        source_dir / "app_core_pt_BR.arb",
        {
            "@@locale": "pt_BR",
            "welcome": "Olá, {name}!",
            "settings": "Configurações",
        },
    )
    write_arb(
        target_dir / "app_core_es_ES.arb",
        {
            "@@locale": "es_ES",
            "welcome": "Hola, {name}!",
        },
    )

    changed = sync_locale_files(tmp_path, "pt_BR")

    assert changed == 1
    target_data = json.loads((target_dir / "app_core_es_ES.arb").read_text(encoding="utf-8"))
    assert target_data["settings"] == "Configurações"


def test_main_validate_command_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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

    exit_code = main(["validate", "--root", str(tmp_path), "--source", "pt_BR"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "placeholder mismatch" in captured.out or "missing keys" in captured.out


def test_main_sync_missing_source_reports_error_without_touching_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_file = tmp_path / "lib" / "l10n" / "europa" / "es_ES" / "app_core_es_ES.arb"
    write_arb(target_file, {"@@locale": "es_ES", "welcome": "Hola, {name}!"})
    bytes_before = target_file.read_bytes()
    files_before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*.arb"))

    exit_code = main(["sync", "--root", str(tmp_path), "--source", "pt_BR"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Source locale 'pt_BR' not found" in captured.out
    assert "Traceback" not in captured.err
    assert target_file.read_bytes() == bytes_before
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*.arb")) == files_before
