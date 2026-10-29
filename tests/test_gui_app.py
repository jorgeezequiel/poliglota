from __future__ import annotations

from pathlib import Path

import pytest

from poliglota import __version__
from poliglota.gui import main as gui_main
from poliglota.gui_app import PoliglotaGUI, build_gui_app


@pytest.mark.unit
def test_gui_package_reports_headless_startup() -> None:
    assert gui_main(["--headless"]) == 0


@pytest.mark.unit
def test_gui_app_builds_without_display() -> None:
    app = build_gui_app(project_root=Path(), headless=True)
    assert isinstance(app, PoliglotaGUI)
    assert app.project_root == Path.cwd()
    assert app.headless is True
    assert app.run() == 0


@pytest.mark.unit
def test_package_version_matches_020() -> None:
    assert __version__ == "0.0.2"
