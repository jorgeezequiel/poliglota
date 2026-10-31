from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from poliglota.gui_config import (
    DEFAULT_THEME,
    DEVICE_CHOICES,
    ENGINE_CHOICES,
    FORMAT_CHOICES,
    GuiState,
    default_state_path,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_default_state_path_honours_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "custom" / "state.json"
    monkeypatch.setenv("POLIGLOTA_GUI_STATE_FILE", str(target))

    assert default_state_path() == target


@pytest.mark.unit
def test_default_state_path_points_to_app_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POLIGLOTA_GUI_STATE_FILE", raising=False)

    resolved = default_state_path()

    assert resolved.name == "gui_state.json"
    assert resolved.parent.name == "poliglota"


@pytest.mark.unit
def test_save_and_load_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.json"
    state = GuiState(
        project_root=str(tmp_path),
        format="yaml",
        source_locale="en",
        target_locale="pt_BR",
        engine="pytorch",
        device="cpu",
        model_name="facebook/nllb-200-distilled-600M",
        dry_run=False,
    )

    assert save_state(state, path) is True
    assert load_state(path) == state


@pytest.mark.unit
def test_load_state_returns_defaults_when_file_is_missing(tmp_path: Path) -> None:
    assert load_state(tmp_path / "absent.json") == GuiState()


@pytest.mark.unit
def test_load_state_ignores_corrupted_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert load_state(path) == GuiState()


@pytest.mark.unit
def test_load_state_requires_a_json_object(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert load_state(path) == GuiState()


@pytest.mark.unit
def test_load_state_ignores_unknown_keys_and_wrong_types(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "format": "json",
                "unknown_key": "ignored",
                "engine": 5,
                "dry_run": "yes",
            },
        ),
        encoding="utf-8",
    )

    state = load_state(path)

    assert state.format == "json"
    assert state.engine == "marian"
    assert state.dry_run is True


@pytest.mark.unit
def test_load_state_falls_back_when_choice_is_not_supported(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"device": "tpu"}), encoding="utf-8")

    assert load_state(path).device == "auto"


@pytest.mark.unit
def test_save_state_reports_failure_instead_of_raising(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")

    assert save_state(GuiState(), blocker / "state.json") is False


@pytest.mark.unit
def test_choice_constants_match_cli_supported_values() -> None:
    assert set(FORMAT_CHOICES) == {"arb", "json", "yaml", "xml"}
    assert set(ENGINE_CHOICES) == {"marian", "pytorch"}
    assert set(DEVICE_CHOICES) == {"auto", "cpu", "cuda", "mps", "gpu"}


@pytest.mark.unit
def test_to_mapping_covers_every_state_field() -> None:
    mapping = GuiState().to_mapping()

    assert set(mapping) == {
        "project_root",
        "format",
        "source_locale",
        "target_locale",
        "engine",
        "device",
        "model_name",
        "dry_run",
        "theme",
        "window_geometry",
    }


@pytest.mark.unit
def test_load_state_falls_back_when_theme_is_not_supported(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"theme": "neon"}), encoding="utf-8")

    assert load_state(path).theme == DEFAULT_THEME


@pytest.mark.unit
def test_save_and_load_state_round_trip_theme_and_geometry(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = GuiState(theme="dark", window_geometry="1100x700+120+80")

    assert save_state(state, path) is True
    restored = load_state(path)
    assert restored.theme == "dark"
    assert restored.window_geometry == "1100x700+120+80"
