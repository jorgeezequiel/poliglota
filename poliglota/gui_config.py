"""Persistence of the desktop GUI form state between sessions.

The GUI is a thin wrapper around the CLI, so nothing here touches business
logic: the module only remembers what the user typed last time (project root,
format, locales, engine, device, model and the dry-run toggle) and restores it
on the next launch.

Two artifacts live side by side: the *state* file (last used form values,
window geometry and the recent-project history) and the *presets* file (named
configurations the user saved on purpose). Both are plain JSON and both fail
soft: a corrupted file never prevents the window from opening.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

logger = logging.getLogger(__name__)

APP_DIRECTORY_NAME = "poliglota"
STATE_FILE_NAME = "gui_state.json"
PRESETS_FILE_NAME = "gui_presets.json"
STATE_FILE_ENV_VAR = "POLIGLOTA_GUI_STATE_FILE"

#: How many project folders the GUI remembers for the history dropdown.
RECENT_PROJECTS_LIMIT = 8

#: Formats offered by the GUI combobox.
FORMAT_CHOICES: tuple[str, ...] = ("arb", "json", "yaml", "xml")
#: Translation engines offered by the GUI combobox.
ENGINE_CHOICES: tuple[str, ...] = ("marian", "pytorch")
#: Devices offered by the GUI combobox.
DEVICE_CHOICES: tuple[str, ...] = ("auto", "cpu", "cuda", "mps", "gpu")
#: Visual themes offered by the GUI.
THEME_CHOICES: tuple[str, ...] = ("light", "dark")
#: Theme used when nothing was saved yet.
DEFAULT_THEME = "light"

_CHOICE_FIELDS: dict[str, tuple[str, ...]] = {
    "format": FORMAT_CHOICES,
    "engine": ENGINE_CHOICES,
    "device": DEVICE_CHOICES,
    "theme": THEME_CHOICES,
}


def default_state_path() -> Path:
    """Return the platform-appropriate path of the persisted GUI state file."""
    override = os.environ.get(STATE_FILE_ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "").strip()
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
        root = Path(xdg_config) if xdg_config else Path.home() / ".config"

    return root / APP_DIRECTORY_NAME / STATE_FILE_NAME


@dataclass(slots=True)
class GuiState:
    """Form state remembered between GUI sessions."""

    project_root: str = ""
    format: str = "arb"
    source_locale: str = "pt_BR"
    target_locale: str = "en_US"
    engine: str = "marian"
    device: str = "auto"
    model_name: str = ""
    dry_run: bool = True
    theme: str = DEFAULT_THEME
    window_geometry: str = ""
    recent_projects: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GuiState:
        """Build a state from raw JSON data, ignoring unknown or invalid entries."""
        defaults = cls()
        values: dict[str, Any] = {}

        for state_field in fields(cls):
            if state_field.name not in data:
                continue
            raw_value = data[state_field.name]
            if state_field.name == "recent_projects":
                values[state_field.name] = _sanitize_recent_projects(raw_value)
                continue
            expected_type = type(getattr(defaults, state_field.name))
            if not isinstance(raw_value, expected_type):
                logger.warning(
                    "Ignoring GUI state key %r: expected %s, got %s",
                    state_field.name,
                    expected_type.__name__,
                    type(raw_value).__name__,
                )
                continue
            values[state_field.name] = raw_value

        state = cls(**values)

        for name, allowed in _CHOICE_FIELDS.items():
            current = getattr(state, name)
            if current not in allowed:
                logger.warning(
                    "Ignoring GUI state key %r: %r is not one of %s",
                    name,
                    current,
                    ", ".join(allowed),
                )
                setattr(state, name, getattr(defaults, name))

        return state

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this state."""
        return {state_field.name: getattr(self, state_field.name) for state_field in fields(self)}


@dataclass(frozen=True, slots=True)
class Preset:
    """A named set of translation options the user can reapply later."""

    name: str
    project_root: str = ""
    format: str = "arb"
    source_locale: str = "pt_BR"
    target_locale: str = "en_US"
    engine: str = "marian"
    device: str = "auto"
    model_name: str = ""
    dry_run: bool = True

    @classmethod
    def from_state(cls, name: str, state: GuiState) -> Preset:
        """Build a preset named ``name`` from the current form state."""
        return cls(
            name=name,
            project_root=state.project_root,
            format=state.format,
            source_locale=state.source_locale,
            target_locale=state.target_locale,
            engine=state.engine,
            device=state.device,
            model_name=state.model_name,
            dry_run=state.dry_run,
        )

    @classmethod
    def from_mapping(cls, name: str, data: Mapping[str, Any]) -> Preset | None:
        """Build a preset from raw JSON data, returning ``None`` when unusable."""
        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            return None

        defaults = cls(name=cleaned_name)
        values: dict[str, Any] = {"name": cleaned_name}

        for preset_field in fields(cls):
            if preset_field.name == "name" or preset_field.name not in data:
                continue
            raw_value = data[preset_field.name]
            expected_type = type(getattr(defaults, preset_field.name))
            if not isinstance(raw_value, expected_type):
                logger.warning(
                    "Ignoring preset %r key %r: expected %s, got %s",
                    cleaned_name,
                    preset_field.name,
                    expected_type.__name__,
                    type(raw_value).__name__,
                )
                continue
            values[preset_field.name] = raw_value

        for choice_name, allowed in _CHOICE_FIELDS.items():
            if choice_name == "theme" or choice_name not in values:
                continue
            if values[choice_name] not in allowed:
                logger.warning(
                    "Ignoring preset %r key %r: %r is not one of %s",
                    cleaned_name,
                    choice_name,
                    values[choice_name],
                    ", ".join(allowed),
                )
                values.pop(choice_name)

        return cls(**values)

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of this preset."""
        return {
            preset_field.name: getattr(self, preset_field.name)
            for preset_field in fields(self)
            if preset_field.name != "name"
        }


def _sanitize_recent_projects(value: object) -> list[str]:
    """Keep only unique, non-empty project paths, capped at the history limit."""
    if not isinstance(value, list):
        return []

    recent: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned and cleaned not in recent:
            recent.append(cleaned)
    return recent[:RECENT_PROJECTS_LIMIT]


def presets_path(state_path: Path | None = None) -> Path:
    """Return the presets file that sits next to the given state file."""
    target = state_path if state_path is not None else default_state_path()
    return target.with_name(PRESETS_FILE_NAME)


def load_state(path: Path | None = None) -> GuiState:
    """Load the persisted state, falling back to defaults when unavailable.

    A missing, unreadable or corrupted file never breaks the GUI: the user
    simply starts from the defaults.
    """
    target = path if path is not None else default_state_path()

    try:
        raw_text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.info("No GUI state file at %s; starting from defaults", target)
        return GuiState()
    except OSError as exc:
        logger.warning("Could not read GUI state file %s: %s", target, exc)
        return GuiState()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("GUI state file %s is not valid JSON: %s", target, exc)
        return GuiState()

    if not isinstance(data, dict):
        logger.warning("GUI state file %s must contain a JSON object", target)
        return GuiState()

    return GuiState.from_mapping(data)


def save_state(state: GuiState, path: Path | None = None) -> bool:
    """Persist the state to disk, returning whether the write succeeded."""
    target = path if path is not None else default_state_path()

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_mapping(), indent=2, ensure_ascii=False)
        target.write_text(f"{payload}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write GUI state file %s: %s", target, exc)
        return False

    logger.debug("GUI state saved to %s", target)
    return True


def load_presets(path: Path | None = None) -> dict[str, Preset]:
    """Load the saved presets, skipping entries that cannot be understood."""
    target = path if path is not None else presets_path()

    try:
        raw_text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.info("No GUI presets file at %s", target)
        return {}
    except OSError as exc:
        logger.warning("Could not read GUI presets file %s: %s", target, exc)
        return {}

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("GUI presets file %s is not valid JSON: %s", target, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning("GUI presets file %s must contain a JSON object", target)
        return {}

    presets: dict[str, Preset] = {}
    for name, payload in data.items():
        if not isinstance(payload, dict):
            logger.warning("Ignoring GUI preset %r: payload is not an object", name)
            continue
        preset = Preset.from_mapping(name, payload)
        if preset is not None:
            presets[preset.name] = preset

    return dict(sorted(presets.items()))


def save_presets(presets: Mapping[str, Preset], path: Path | None = None) -> bool:
    """Persist the presets to disk, returning whether the write succeeded."""
    target = path if path is not None else presets_path()

    payload = {
        name: preset.to_mapping() for name, preset in sorted(presets.items()) if name.strip()
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, ensure_ascii=False)
        target.write_text(f"{serialized}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write GUI presets file %s: %s", target, exc)
        return False

    logger.debug("GUI presets saved to %s", target)
    return True
