from __future__ import annotations

from pathlib import Path

import pytest

from poliglota import __version__
from poliglota.gui import main as gui_main
from poliglota.gui_app import PoliglotaGUI, build_gui_app


class DummyVar:
    def __init__(self, value: str | bool = "") -> None:
        self.value = value

    def get(self) -> str | bool:
        return self.value

    def set(self, value: str | bool) -> None:
        self.value = value


class DummyWidget:
    def __init__(self) -> None:
        self.state: str | None = None

    def configure(self, **kwargs: object) -> None:
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class DummyRoot:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []
        self.closed = False
        self._exists = True

    def after(
        self,
        _delay: int,
        callback: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append((callback, args, kwargs))
        return object()

    def after_cancel(self, _callback_id: object) -> None:
        self.closed = True

    def winfo_exists(self) -> bool:
        return self._exists and not self.closed

    def destroy(self) -> None:
        self.closed = True
        self._exists = False


class DummyText:
    def __init__(self) -> None:
        self.text = ""

    def delete(self, *_args: object) -> None:
        self.text = ""

    def insert(self, *_args: object) -> None:
        self.text = "updated"

    def see(self, *_args: object) -> None:
        return None


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


@pytest.mark.unit
def test_gui_choose_project_dir_updates_selected_path(monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_root = Path("C:/temp")
    app = build_gui_app(project_root=tmp_root, headless=False)
    app.root = DummyRoot()
    app.project_var = DummyVar(str(tmp_root / "original"))
    monkeypatch.setattr(
        "poliglota.gui_app.filedialog.askdirectory",
        lambda **_: str(tmp_root / "selected"),
    )

    app._choose_project_dir()

    assert app.project_var.get() == str(tmp_root / "selected")


@pytest.mark.unit
def test_gui_choose_project_dir_ignores_cancelled_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_root = Path("C:/temp")
    app = build_gui_app(project_root=tmp_root, headless=False)
    app.root = object()
    app.project_var = DummyVar(str(tmp_root / "original"))
    monkeypatch.setattr("poliglota.gui_app.filedialog.askdirectory", lambda **_: "")

    app._choose_project_dir()

    assert app.project_var.get() == str(tmp_root / "original")


@pytest.mark.unit
def test_gui_translate_command_uses_user_text() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.translation_var = DummyVar("Olá, mundo!")
    app.source_var = DummyVar("pt_BR")
    app.target_var = DummyVar("en_US")
    app.engine_var = DummyVar("pytorch")
    app.device_var = DummyVar("cpu")
    app.model_var = DummyVar("facebook/nllb-200-distilled-600M")

    command = app._build_translate_command()

    assert command == [
        "translate",
        "Olá, mundo!",
        "--source",
        "pt_BR",
        "--target",
        "en_US",
        "--engine",
        "pytorch",
        "--device",
        "cpu",
        "--model",
        "facebook/nllb-200-distilled-600M",
    ]


@pytest.mark.unit
def test_gui_operation_state_prevents_overlap() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    widget = DummyWidget()
    app._interactive_widgets = [widget]
    app._action_buttons = [DummyWidget()]

    assert app._begin_operation("busy") is True
    assert app._is_running is True
    assert app._begin_operation("busy again") is False

    app._complete_operation(status_message="done")

    assert app._is_running is False
    assert widget.state == "normal"


@pytest.mark.unit
def test_gui_dispatch_command_updates_status_through_root_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")
    app.output_text = DummyText()
    app._interactive_widgets = []
    app._action_buttons = []
    monkeypatch.setattr(app, "_run_cli_command", lambda *args, **kwargs: (0, "resultado ok"))

    app._dispatch_command(
        ["validate", "--root", "C:/temp"],
        busy_message="Validando...",
        success_message="Concluído.",
    )
    app._worker_thread.join(timeout=1)
    while not app._message_queue.empty():
        app._process_message_queue()

    assert app.status_var.get() == "Concluído."
    assert app.output_text.text == "updated"


@pytest.mark.unit
def test_gui_queue_messages_are_processed_on_main_thread() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")
    app.output_text = DummyText()
    app._interactive_widgets = []
    app._action_buttons = []

    app._message_queue.put(("status", "em andamento"))
    app._message_queue.put(("result", "resultado"))
    app._process_message_queue()

    assert app.status_var.get() == "em andamento"
    assert app.output_text.text == "updated"


@pytest.mark.unit
def test_gui_window_close_prevents_ui_updates_after_destroy() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")
    app.output_text = DummyText()
    app._interactive_widgets = []
    app._action_buttons = []
    app._window_closed = False
    app._close_window()

    app._message_queue.put(("status", "deve ser ignorado"))
    app._message_queue.put(("result", "deve ser ignorado"))
    app._process_message_queue()

    assert app.status_var.get() == "idle"
    assert app.output_text.text == ""
