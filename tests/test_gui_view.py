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
    Tooltip,
    configure_dpi_scaling,
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

    def bind(
        self,
        sequence: str,
        handler: Callable[[object], str],
        *_args: object,
        **_kwargs: object,
    ) -> None:
        self.bindings[sequence] = handler


class DummyText:
    def __init__(self) -> None:
        self.text = ""
        self.seen = False
        self.inserted_tags: list[object] = []

    def delete(self, *_args: object) -> None:
        self.text = ""

    def insert(self, _index: object, value: str, tags: object = ()) -> None:
        self.text += value
        self.inserted_tags.append(tags)

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
        project_history_selected=record("project_history_selected"),
        cancel=record("cancel"),
        restore_defaults=record("restore_defaults"),
        copy_output=record("copy_output"),
        save_output=record("save_output"),
        clear_output=record("clear_output"),
        apply_preset=record("apply_preset"),
        save_preset=record("save_preset"),
        delete_preset=record("delete_preset"),
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

    assert set(root.bindings) == {"<Control-o>", "<Control-l>", "<F5>", "<Escape>"}
    assert "<Return>" in entry.bindings

    assert root.bindings["<Control-o>"](object()) == "break"
    assert root.bindings["<Control-l>"](object()) == "break"
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


class StatefulText(DummyText):
    def __init__(self) -> None:
        super().__init__()
        self.state = "normal"
        self.states: list[str] = []

    def configure(self, **kwargs: object) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])
            self.states.append(self.state)

    def get(self, *_args: object) -> str:
        return f"{self.text}\n"


class EditableText:
    def __init__(self) -> None:
        self.text = ""
        self.state = "normal"
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)
        if "state" in kwargs:
            self.state = str(kwargs["state"])

    def cget(self, _option: str) -> str:
        return self.state

    def get(self, *_args: object) -> str:
        return self.text

    def delete(self, *_args: object) -> None:
        self.text = ""

    def insert(self, _index: object, value: str) -> None:
        self.text += value


class TooltipWidget(DummyEntry):
    def __init__(self) -> None:
        super().__init__()
        self.after_calls: list[tuple[int, Callable[[], None]]] = []
        self.cancelled: list[object] = []

    def after(self, delay: int, callback: Callable[[], None]) -> object:
        self.after_calls.append((delay, callback))
        return object()

    def after_cancel(self, callback_id: object) -> None:
        self.cancelled.append(callback_id)


class ModifiedText(EditableText):
    def __init__(self) -> None:
        super().__init__()
        self.modified = True

    def edit_modified(self, arg: bool | None = None) -> bool:
        if arg is None:
            return self.modified
        self.modified = arg
        return self.modified


class RecordingVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class ScaledRoot:
    def __init__(self, pixels_per_inch: float) -> None:
        self.pixels_per_inch = pixels_per_inch
        self.tk = self
        self.calls: list[tuple[object, ...]] = []

    def winfo_fpixels(self, _unit: str) -> float:
        return self.pixels_per_inch

    def call(self, *args: object) -> None:
        self.calls.append(args)


@pytest.mark.unit
def test_tooltip_binds_and_stores_its_text() -> None:
    widget = TooltipWidget()
    tooltip = Tooltip(widget, "dica de uso", delay_ms=100)

    assert tooltip.text == "dica de uso"
    assert set(widget.bindings) == {"<Enter>", "<Leave>", "<ButtonPress>"}

    widget.bindings["<Enter>"](object())

    assert widget.after_calls[0][0] == 100

    tooltip.hide()

    assert tooltip._window is None
    assert widget.cancelled


@pytest.mark.unit
def test_tooltip_is_a_no_op_without_binding_support() -> None:
    tooltip = Tooltip(object(), "dica")

    tooltip._schedule()
    tooltip.hide()

    assert tooltip._window is None


@pytest.mark.unit
def test_view_output_writes_unlock_and_relock_the_pane() -> None:
    view = GuiView()
    text = StatefulText()
    view.output_text = text  # type: ignore[assignment]

    assert view.show_output("resultado") is True
    assert text.text == "resultado"
    assert text.states[-1] == "disabled"

    assert view.append_output("linha") is True
    assert text.states[-1] == "disabled"

    assert view.clear_output() is True
    assert text.states[-1] == "disabled"


@pytest.mark.unit
def test_view_output_content_strips_the_trailing_newline() -> None:
    view = GuiView()
    text = StatefulText()
    text.text = "conteúdo"
    view.output_text = text  # type: ignore[assignment]

    assert view.output_content() == "conteúdo"


@pytest.mark.unit
def test_view_output_content_is_empty_without_a_getter() -> None:
    view = GuiView()
    view.output_text = DummyText()  # type: ignore[assignment]

    assert view.output_content() == ""


@pytest.mark.unit
def test_view_multiline_field_uses_highlight_instead_of_entry_style() -> None:
    view = GuiView()
    text = EditableText()
    view.multiline_fields = {"translation": text}
    view.field_widgets = {"translation": text}

    view.mark_invalid({"translation"})

    assert text.options["highlightcolor"] == THEMES[DEFAULT_THEME].error
    assert "style" not in text.options

    view.mark_invalid(set())

    assert text.options["highlightcolor"] == THEMES[DEFAULT_THEME].accent


@pytest.mark.unit
def test_view_sets_and_reads_the_multiline_text() -> None:
    view = GuiView()
    text = EditableText()
    view.translation_text = text  # type: ignore[assignment]

    view.set_translation_text("primeira linha\nsegunda linha")

    assert text.text == "primeira linha\nsegunda linha"
    assert text.state == "normal"
    assert view.translation_content() == "primeira linha\nsegunda linha"

    view.set_translation_text("primeira linha\nsegunda linha")

    assert view.translation_content() == "primeira linha\nsegunda linha"


@pytest.mark.unit
def test_view_multiline_helpers_are_no_ops_without_a_widget() -> None:
    view = GuiView()

    view.set_translation_text("texto")

    assert view.translation_content() == ""


@pytest.mark.unit
def test_view_syncs_typed_text_into_the_bound_variable() -> None:
    view = GuiView()
    text = ModifiedText()
    text.text = "digitado"
    variable = RecordingVar()
    view.translation_text = text  # type: ignore[assignment]
    view._translation_variable = variable

    view._sync_translation_text()

    assert variable.value == "digitado"
    assert text.modified is False

    text.modified = False
    view._sync_translation_text()

    assert variable.value == "digitado"


@pytest.mark.unit
def test_configure_dpi_scaling_applies_the_monitor_ratio() -> None:
    root = ScaledRoot(144.0)

    scaling = configure_dpi_scaling(root)

    assert scaling == pytest.approx(2.0)
    assert root.calls == [("tk", "scaling", 2.0)]


@pytest.mark.unit
def test_configure_dpi_scaling_is_a_no_op_without_root_support() -> None:
    assert configure_dpi_scaling(object()) is None


@pytest.mark.unit
def test_configure_dpi_scaling_rejects_invalid_pixel_ratios() -> None:
    assert configure_dpi_scaling(ScaledRoot(0.0)) is None
