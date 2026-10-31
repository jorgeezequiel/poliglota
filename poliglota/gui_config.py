"""Persistence of the desktop GUI form state between sessions.

The GUI is a thin wrapper around the CLI, so nothing here touches business
logic: the module only remembers what the user typed last time (project root,
format, locales, engine, device, model and the dry-run toggle) and restores it
on the next launch.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

logger = logging.getLogger(__name__)

APP_DIRECTORY_NAME = "poliglota"
STATE_FILE_NAME = "gui_state.json"
STATE_FILE_ENV_VAR = "POLIGLOTA_GUI_STATE_FILE"

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

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> GuiState:
        """Build a state from raw JSON data, ignoring unknown or invalid entries."""
        defaults = cls()
        values: dict[str, Any] = {}

        for state_field in fields(cls):
            if state_field.name not in data:
                continue
            raw_value = data[state_field.name]
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
