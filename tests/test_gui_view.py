from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from poliglota.gui_config import DEFAULT_THEME
from poliglota.gui_view import (
    DEFAULT_GEOMETRY,
    INVALID_ENTRY_STYLE,
    NORMAL_ENTRY_STYLE,
    THEMES,
    GuiActions,
    GuiView,
    normalize_geometry,
    resolve_theme,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class DummyEntry:
    def __init__(self) -> None:
        self.styles: list[object] = []
        self.focused = False
        self.bindings: dict[str, Callable[[object], str]] = {}

    def configure(self, **kwargs: object) -> None:
        if "style" in kwargs:
            self.styles.append(kwargs["style"])

    def focus_set(self) -> None:
        self.focused = True

    def bind(self, sequence: str, handler: Callable[[object], str]) -> None:
        self.bindings[sequence] = handler


class DummyText:
    def __init__(self) -> None:
        self.text = ""
        self.seen = False

    def delete(self, *_args: object) -> None:
        self.text = ""

    def insert(self, _index: object, value: str) -> None:
        self.text += value

    def see(self, *_args: object) -> None:
        self.seen = True


class DummyProgress:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.interval: int | None = None
        self.stopped = False

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)

    def start(self, interval: int) -> None:
        self.interval = interval

    def stop(self) -> None:
        self.stopped = True


class DummyButton:
    def __init__(self) -> None:
        self.state: str | None = None

    def configure(self, **kwargs: object) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class DummyBindRoot:
    def __init__(self) -> None:
        self.bindings: dict[str, Callable[[object], str]] = {}

    def bind(self, sequence: str, handler: Callable[[object], str]) -> None:
        self.bindings[sequence] = handler


def _actions(calls: list[str]) -> GuiActions:
    def record(name: str) -> Callable[[], None]:
        def callback() -> None:
            calls.append(name)

        return callback

    return GuiActions(
        validate=record("validate"),
        sync=record("sync"),
        list_locales=record("list_locales"),
        translate=record("translate"),
        translate_project=record("translate_project"),
        choose_project=record("choose_project"),
        cancel=record("cancel"),
    )


@pytest.mark.unit
def test_normalize_geometry_keeps_a_valid_value() -> None:
    assert (
        normalize_geometry("1000x700+120+80", screen_width=1920, screen_height=1080)
        == "1000x700+120+80"
    )


@pytest.mark.unit
def test_normalize_geometry_accepts_size_without_position() -> None:
    assert normalize_geometry("1000x700", screen_width=1920, screen_height=1080) == "1000x700"


@pytest.mark.unit
@pytest.mark.parametrize("geometry", ["", "   ", "abc", "1000", "1000x700+", "1000x700+1+2+3"])
def test_normalize_geometry_falls_back_for_malformed_values(geometry: str) -> None:
    assert normalize_geometry(geometry, screen_width=1920, screen_height=1080) == DEFAULT_GEOMETRY


@pytest.mark.unit
def test_normalize_geometry_enforces_minimum_size() -> None:
    assert normalize_geometry("200x100", screen_width=1920, screen_height=1080) == "760x500"


@pytest.mark.unit
def test_normalize_geometry_clamps_size_to_the_screen() -> None:
    assert (
        normalize_geometry("5000x4000+0+0", screen_width=1920, screen_height=1080)
        == "1920x1080+0+0"
    )


@pytest.mark.unit
def test_normalize_geometry_resets_offscreen_position() -> None:
    assert (
        normalize_geometry("800x600+5000+4000", screen_width=1920, screen_height=1080)
        == "800x600+40+40"
    )


@pytest.mark.unit
def test_normalize_geometry_resets_negative_position() -> None:
    assert (
        normalize_geometry("800x600-100-100", screen_width=1920, screen_height=1080)
        == "800x600+40+40"
    )


@pytest.mark.unit
def test_resolve_theme_returns_known_theme() -> None:
    assert resolve_theme("dark").name == "dark"
    assert resolve_theme("light").name == "light"


@pytest.mark.unit
def test_resolve_theme_falls_back_to_the_default() -> None:
    assert resolve_theme("neon").name == DEFAULT_THEME


@pytest.mark.unit
def test_themes_are_distinct() -> None:
    assert set(THEMES) == {"light", "dark"}
    assert THEMES["light"].background != THEMES["dark"].background
    assert THEMES["light"].foreground != THEMES["dark"].foreground


@pytest.mark.unit
def test_view_starts_empty_without_a_root() -> None:
    view = GuiView()

    assert view.root is None
    assert view.output_text is None
    assert view.validation_label is None
    assert view.progress is None
    assert view.cancel_button is None
    assert view.theme == DEFAULT_THEME


@pytest.mark.unit
def test_view_theme_can_be_applied_without_widgets() -> None:
    view = GuiView()

    assert view.apply_theme("dark") == "dark"
    assert view.theme == "dark"
    assert view.apply_theme("neon") == DEFAULT_THEME


@pytest.mark.unit
def test_view_output_helpers_are_no_ops_without_a_text_widget() -> None:
    view = GuiView()

    assert view.show_output("texto") is True
    assert view.append_output("linha") is True
    assert view.clear_output() is True


@pytest.mark.unit
def test_view_show_output_replaces_content() -> None:
    view = GuiView()
    text = DummyText()
    view.output_text = text  # type: ignore[assignment]

    assert view.show_output("  resultado  ") is True
    assert text.text == "resultado"
    assert text.seen is True

    assert view.show_output("   ") is True
    assert text.text == "Nenhuma saída do comando."


@pytest.mark.unit
def test_view_append_output_accumulates_lines() -> None:
    view = GuiView()
    text = DummyText()
    view.output_text = text  # type: ignore[assignment]

    assert view.append_output("linha 1") is True
    assert view.append_output("linha 2") is True

    assert text.text == "linha 1\nlinha 2\n"


@pytest.mark.unit
def test_view_reports_a_broken_output_widget() -> None:
    class BrokenText(DummyText):
        def insert(self, _index: object, _value: str) -> None:
            msg = "widget destroyed"
            raise RuntimeError(msg)

    view = GuiView()
    view.output_text = BrokenText()  # type: ignore[assignment]

    assert view.show_output("texto") is False
    assert view.append_output("linha") is False


@pytest.mark.unit
def test_view_marks_and_clears_invalid_entries() -> None:
    view = GuiView()
    project = DummyEntry()
    source = DummyEntry()
    view.field_widgets = {"project": project, "source": source}

    view.mark_invalid({"project"})

    assert project.styles == [INVALID_ENTRY_STYLE]
    assert source.styles == [NORMAL_ENTRY_STYLE]

    view.mark_invalid(set())

    assert project.styles[-1] == NORMAL_ENTRY_STYLE


@pytest.mark.unit
def test_view_focuses_a_registered_field() -> None:
    view = GuiView()
    entry = DummyEntry()
    view.field_widgets = {"project": entry}

    view.focus_field("project")
    view.focus_field("missing")

    assert entry.focused is True


@pytest.mark.unit
def test_view_toggles_progress_and_cancel_button() -> None:
    view = GuiView()
    progress = DummyProgress()
    button = DummyButton()
    view.progress = progress  # type: ignore[assignment]
    view.cancel_button = button  # type: ignore[assignment]

    view.set_busy(busy=True)

    assert progress.options["mode"] == "indeterminate"
    assert progress.interval is not None
    assert button.state == "normal"

    view.set_busy(busy=False)

    assert progress.stopped is True
    assert progress.options["mode"] == "determinate"
    assert progress.options["value"] == 0
    assert button.state == "disabled"


@pytest.mark.unit
def test_view_shortcuts_dispatch_actions() -> None:
    calls: list[str] = []
    view = GuiView()
    root = DummyBindRoot()
    entry = DummyEntry()
    view.root = root  # type: ignore[assignment]
    view.field_widgets = {"project": entry}
    view._actions = _actions(calls)

    view.bind_shortcuts()

    assert set(root.bindings) == {"<Control-o>", "<F5>", "<Escape>"}
    assert "<Return>" in entry.bindings

    assert root.bindings["<Control-o>"](object()) == "break"
    assert root.bindings["<F5>"](object()) == "break"
    assert root.bindings["<Escape>"](object()) == "break"
    assert entry.bindings["<Return>"](object()) == "break"

    assert calls == ["choose_project", "validate", "cancel", "validate"]


@pytest.mark.unit
def test_view_geometry_is_unknown_without_a_root() -> None:
    view = GuiView()

    assert view.geometry() == ""
    assert view.apply_geometry("1000x700+10+10") == DEFAULT_GEOMETRY


@pytest.mark.unit
def test_view_geometry_tolerates_a_root_without_geometry_support() -> None:
    view = GuiView()
    view.root = object()  # type: ignore[assignment]

    assert view.geometry() == ""
    assert view.apply_geometry("1000x700+10+10") == "1000x700+10+10"
