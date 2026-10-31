from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from poliglota import __version__
from poliglota.gui import main as gui_main
from poliglota.gui_app import PoliglotaGUI, build_gui_app, enable_high_dpi
from poliglota.gui_config import DEFAULT_THEME, GuiState, load_state


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
def test_gui_default_model_uses_shared_translation_plan() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.source_var = DummyVar("pt_BR")
    app.target_var = DummyVar("en_US")
    app.model_var = DummyVar("")
    app.device_var = DummyVar("cpu")

    assert app._resolve_default_model_for_pair("pt_BR", "en_US") == "Helsinki-NLP/opus-mt-tc-big-en-pt"
    assert app._resolve_default_model_for_targets("pt_BR", ["en_US"]) == "Helsinki-NLP/opus-mt-tc-big-en-pt"


@pytest.mark.unit
def test_gui_project_source_is_revalidated_from_project_files(tmp_path: Path) -> None:
    project = tmp_path / "l10n"
    project.mkdir()
    source = project / "pt_BR.json"
    source.write_text('{"hello": "olá"}', encoding="utf-8")
    target = project / "en_US.json"
    target.write_text('{"hello": "hello"}', encoding="utf-8")

    app = build_gui_app(project_root=tmp_path, headless=True)
    app.project_var = DummyVar(str(project))
    app.source_var = DummyVar("en_US")
    app.format_var = DummyVar("json")
    app.target_var = DummyVar("en_US")
    app.model_var = DummyVar("")
    app.device_var = DummyVar("cpu")

    resolved_source = app._resolve_project_source_locale(project, "json")
    assert resolved_source == "pt_BR"
    built = app._build_translate_project_command()
    assert "--source" in built
    assert built[built.index("--source") + 1] == "pt_BR"


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


class RecordingText:
    def __init__(self) -> None:
        self.text = ""

    def delete(self, *_args: object) -> None:
        self.text = ""

    def insert(self, _index: object, value: str) -> None:
        self.text += value

    def see(self, *_args: object) -> None:
        return None


class DummyProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def poll(self) -> int | None:
        return 1 if self.terminated else None


class DummyGeometryRoot(DummyRoot):
    def __init__(self, geometry: str) -> None:
        super().__init__()
        self._geometry = geometry

    def geometry(self) -> str:
        return self._geometry


def _build_valid_app(tmp_path: Path) -> PoliglotaGUI:
    app = build_gui_app(
        project_root=tmp_path,
        headless=True,
        state_path=tmp_path / "state.json",
    )
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")
    app.validation_var = DummyVar("")
    app.project_var = DummyVar(str(tmp_path))
    app.source_var = DummyVar("pt_BR")
    app.target_var = DummyVar("en_US")
    app.model_var = DummyVar("")
    return app


@pytest.mark.unit
def test_gui_var_value_handles_missing_variable() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)

    assert app._var_value(None) == ""
    assert app._var_value(DummyVar("  pt_BR  ")) == "pt_BR"


@pytest.mark.unit
def test_gui_validate_form_reports_invalid_project(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.project_var = DummyVar(str(tmp_path / "missing"))

    assert app._validate_form() is False
    assert "Corrija os campos" in str(app.status_var.get())
    assert str(app.validation_var.get()).startswith("✗ Projeto")


@pytest.mark.unit
def test_gui_validate_form_accepts_valid_configuration(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)

    assert app._validate_form() is True
    assert app.validation_var.get() == "✓ Configuração válida."


@pytest.mark.unit
def test_gui_validation_summarizes_multiple_problems(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.project_var = DummyVar("")
    app.target_var = DummyVar("")

    app._refresh_validation()

    message = str(app.validation_var.get())
    assert "outro(s) campo(s)" in message


@pytest.mark.unit
def test_gui_handle_validate_blocks_dispatch_when_form_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.project_var = DummyVar("")
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_validate()

    assert dispatched == []


@pytest.mark.unit
def test_gui_handle_validate_blocks_dispatch_when_source_locale_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.source_var = DummyVar("pt BR!")
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_validate()

    assert dispatched == []


@pytest.mark.unit
def test_gui_translate_is_not_blocked_by_invalid_project_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.project_var = DummyVar("")
    app.translation_var = DummyVar("Olá mundo")
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_translate()

    assert len(dispatched) == 1
    assert dispatched[0][0] == "translate"


@pytest.mark.unit
def test_gui_list_locales_ignores_invalid_model_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.model_var = DummyVar("modelo com espaço")
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_list_locales()

    assert len(dispatched) == 1
    assert dispatched[0][0] == "list-locales"


@pytest.mark.unit
def test_gui_handle_validate_dispatches_when_form_is_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_validate()

    assert dispatched == [
        [
            "validate",
            "--root",
            str(tmp_path),
            "--source",
            "pt_BR",
            "--format",
            "arb",
        ],
    ]


@pytest.mark.unit
def test_gui_handle_translate_requires_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()
    app.translation_var = DummyVar("   ")
    dispatched: list[list[str]] = []
    monkeypatch.setattr(app, "_dispatch_command", lambda command, **_: dispatched.append(command))

    app._handle_translate()

    assert dispatched == []
    assert "Informe o texto para tradução." in app.output_text.text


@pytest.mark.unit
def test_gui_current_state_reflects_widget_values(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.format_var = DummyVar("json")
    app.engine_var = DummyVar("pytorch")
    app.device_var = DummyVar("cpu")
    app.model_var = DummyVar("facebook/nllb-200-distilled-600M")
    app.sync_dry_run_var = DummyVar(value=False)

    state = app._current_state()

    assert state.project_root == str(tmp_path)
    assert state.format == "json"
    assert state.engine == "pytorch"
    assert state.device == "cpu"
    assert state.model_name == "facebook/nllb-200-distilled-600M"
    assert state.dry_run is False


@pytest.mark.unit
def test_gui_save_state_now_persists_form_values(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app._ui_built = True
    app.format_var = DummyVar("yaml")

    app._save_state_now()

    state = load_state(tmp_path / "state.json")
    assert state.project_root == str(tmp_path)
    assert state.format == "yaml"


@pytest.mark.unit
def test_gui_save_state_now_is_skipped_before_ui_is_built(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)

    app._save_state_now()

    assert (tmp_path / "state.json").exists() is False


@pytest.mark.unit
def test_gui_close_window_flushes_pending_state(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app._ui_built = True
    app.source_var = DummyVar("es")

    app._close_window()

    assert load_state(tmp_path / "state.json").source_locale == "es"


@pytest.mark.unit
def test_gui_error_message_is_presented_as_actionable_report(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()
    app._message_queue.put(("error", ("No ARB files found under C:/project.", 1)))

    app._process_message_queue()

    assert "Nenhum arquivo de tradução encontrado" in app.output_text.text
    assert "Sugestão" in app.output_text.text


@pytest.mark.unit
def test_gui_dispatch_failure_publishes_categorized_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()
    monkeypatch.setattr(
        app,
        "_run_cli_command",
        lambda *args, **kwargs: (1, "ModuleNotFoundError: No module named 'torch'"),
    )

    app._dispatch_command(
        ["translate", "texto"],
        busy_message="Traduzindo...",
        success_message="Concluído.",
    )
    app._worker_thread.join(timeout=1)
    while not app._message_queue.empty():
        app._process_message_queue()

    assert "Dependência opcional não instalada" in str(app.status_var.get())
    assert "Dependência opcional não instalada" in app.output_text.text


@pytest.mark.unit
def test_configure_logging_places_log_next_to_state_file(tmp_path: Path) -> None:
    import importlib
    import logging

    gui_module = importlib.import_module("poliglota.gui")
    package_logger = logging.getLogger("poliglota")
    previous_handlers = list(package_logger.handlers)

    try:
        log_path = gui_module._configure_logging(tmp_path / "custom" / "state.json")
    finally:
        for handler in list(package_logger.handlers):
            if handler not in previous_handlers:
                handler.close()
                package_logger.removeHandler(handler)

    assert log_path is not None
    assert log_path == tmp_path / "custom" / "gui.log"
    assert log_path.exists() is True


@pytest.mark.unit
def test_gui_cancel_operation_terminates_running_process() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")
    process = DummyProcess()
    app._process = process  # type: ignore[assignment]
    app._is_running = True

    app._cancel_operation()

    assert app._cancel_requested is True
    assert process.terminated is True
    assert app.status_var.get() == "Cancelando operação..."


@pytest.mark.unit
def test_gui_cancel_operation_is_ignored_when_idle() -> None:
    app = build_gui_app(project_root=Path("C:/temp"), headless=True)
    app.root = DummyRoot()
    app.status_var = DummyVar("idle")

    app._cancel_operation()

    assert app._cancel_requested is False
    assert app.status_var.get() == "idle"


@pytest.mark.unit
def test_gui_dispatch_reports_cancelled_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()

    def fake_run(*_args: object, **_kwargs: object) -> tuple[int, str]:
        app._cancel_requested = True
        return 1, ""

    monkeypatch.setattr(app, "_run_cli_command", fake_run)

    app._dispatch_command(
        ["validate", "--root", str(tmp_path)],
        busy_message="Validando...",
        success_message="Concluído.",
    )
    app._worker_thread.join(timeout=1)
    while not app._message_queue.empty():
        app._process_message_queue()

    assert app.status_var.get() == "Operação cancelada."
    assert "[Operação cancelada pelo usuário]" in app.output_text.text


@pytest.mark.unit
def test_gui_streams_output_lines_before_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()

    def fake_run(
        *_args: object,
        on_line: object = None,
        **_kwargs: object,
    ) -> tuple[int, str]:
        assert callable(on_line)
        on_line("linha 1")
        on_line("linha 2")
        return 0, "linha 1\nlinha 2"

    monkeypatch.setattr(app, "_run_cli_command", fake_run)

    app._dispatch_command(
        ["validate", "--root", str(tmp_path)],
        busy_message="Validando...",
        success_message="Concluído.",
    )
    app._worker_thread.join(timeout=1)
    while not app._message_queue.empty():
        app._process_message_queue()

    assert "linha 1" in app.output_text.text
    assert "linha 2" in app.output_text.text
    assert app.status_var.get() == "Concluído."


@pytest.mark.unit
def test_gui_theme_change_applies_and_persists(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.theme_var = DummyVar("dark")
    app._ui_built = True

    app._on_theme_changed()

    assert app.view.theme == "dark"
    assert app._current_state().theme == "dark"


@pytest.mark.unit
def test_gui_theme_change_falls_back_to_default(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.theme_var = DummyVar("neon")
    app._ui_built = True

    app._on_theme_changed()

    assert app.view.theme == DEFAULT_THEME
    assert app.theme_var.get() == DEFAULT_THEME


@pytest.mark.unit
def test_gui_current_state_reads_window_geometry(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.root = DummyGeometryRoot("1000x700+50+60")

    assert app._current_state().window_geometry == "1000x700+50+60"


@pytest.mark.unit
def test_gui_current_state_keeps_previous_geometry_when_root_has_none(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.state = GuiState(window_geometry="900x600+10+20")

    assert app._current_state().window_geometry == "900x600+10+20"


@pytest.mark.unit
def test_gui_run_cli_command_streams_help_output() -> None:
    repository_root = Path(__file__).resolve().parent.parent
    app = build_gui_app(project_root=repository_root, headless=True)
    lines: list[str] = []

    exit_code, output = app._run_cli_command("--help", on_line=lines.append)

    assert exit_code == 0
    assert lines
    assert "usage" in output.lower()


class GettableText(RecordingText):
    def get(self, *_args: object) -> str:
        return self.text


class EditableText:
    def __init__(self) -> None:
        self.text = ""
        self.state = "normal"

    def configure(self, **kwargs: object) -> None:
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


class ClipboardRoot(DummyRoot):
    def __init__(self) -> None:
        super().__init__()
        self.clipboard = ""

    def clipboard_clear(self) -> None:
        self.clipboard = ""

    def clipboard_append(self, value: str) -> None:
        self.clipboard += value


@pytest.mark.unit
def test_gui_elapsed_tick_updates_the_status_line(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)

    assert app._begin_operation("Validando recursos...") is True
    elapsed_callback = app.root.calls[0][0]  # type: ignore[union-attr]
    elapsed_callback()

    message = str(app.status_var.get())
    assert message.startswith("Validando recursos... (")
    assert message.endswith("s)")

    app._complete_operation(status_message="Concluído.")
    elapsed_callback()

    assert app.status_var.get() == "Concluído."


@pytest.mark.unit
def test_gui_copy_output_uses_the_clipboard(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.root = ClipboardRoot()
    app.output_text = GettableText()
    app.output_text.text = "resultado da validação"

    app._copy_output()

    assert app.root.clipboard == "resultado da validação"
    assert "copiada" in str(app.status_var.get())


@pytest.mark.unit
def test_gui_copy_output_reports_an_empty_pane(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.root = ClipboardRoot()
    app.output_text = GettableText()

    app._copy_output()

    assert app.root.clipboard == ""
    assert "Não há saída" in str(app.status_var.get())


@pytest.mark.unit
def test_gui_save_output_writes_the_selected_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = GettableText()
    app.output_text.text = "conteúdo da saída"
    target = tmp_path / "saida.txt"
    monkeypatch.setattr(
        "poliglota.gui_app.filedialog.asksaveasfilename",
        lambda **_: str(target),
    )

    app._save_output()

    assert target.read_text(encoding="utf-8") == "conteúdo da saída\n"
    assert "Saída salva" in str(app.status_var.get())


@pytest.mark.unit
def test_gui_save_output_ignores_a_cancelled_dialog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = GettableText()
    app.output_text.text = "conteúdo"
    monkeypatch.setattr("poliglota.gui_app.filedialog.asksaveasfilename", lambda **_: "")

    app._save_output()

    assert app.status_var.get() == "Salvamento cancelado."


@pytest.mark.unit
def test_gui_clear_output_button_empties_the_pane(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.output_text = RecordingText()
    app.output_text.text = "texto antigo"

    app._handle_clear_output()

    assert app.output_text.text == ""
    assert app.status_var.get() == "Saída limpa."


@pytest.mark.unit
def test_gui_close_window_can_be_cancelled_while_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app._is_running = True
    monkeypatch.setattr("poliglota.gui_app.messagebox.askyesno", lambda *_, **__: False)

    app._close_window()

    assert app.root.closed is False  # type: ignore[union-attr]
    assert app._window_closed is False


@pytest.mark.unit
def test_gui_close_window_proceeds_when_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _build_valid_app(tmp_path)
    app._is_running = True
    monkeypatch.setattr("poliglota.gui_app.messagebox.askyesno", lambda *_, **__: True)

    app._close_window()

    assert app.root.closed is True  # type: ignore[union-attr]
    assert app._window_closed is True


@pytest.mark.unit
def test_gui_restore_defaults_keeps_the_current_theme(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.format_var = DummyVar("json")
    app.source_var = DummyVar("es")
    app.target_var = DummyVar("fr")
    app.engine_var = DummyVar("pytorch")
    app.device_var = DummyVar("cuda")
    app.model_var = DummyVar("modelo")
    app.sync_dry_run_var = DummyVar(value=False)
    app.translation_var = DummyVar("texto")
    app.theme_var = DummyVar("dark")

    app._restore_defaults()

    assert app.project_var.get() == str(tmp_path)
    assert app.format_var.get() == "arb"
    assert app.source_var.get() == ""
    assert app.target_var.get() == ""
    assert app.engine_var.get() == "marian"
    assert app.device_var.get() == "auto"
    assert app.model_var.get() == ""
    assert app.sync_dry_run_var.get() is True
    assert app.translation_var.get() == ""
    assert app.theme_var.get() == "dark"
    assert app.status_var.get() == "Padrões restaurados."


@pytest.mark.unit
def test_gui_refresh_validation_includes_a_filled_text_field(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.translation_var = DummyVar("Olá, mundo!")

    app._refresh_validation()

    assert app._validation_results["translation"].is_valid is True
    assert app.validation_var.get() == "✓ Configuração válida."


@pytest.mark.unit
def test_gui_refresh_validation_skips_an_empty_text_field(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app.translation_var = DummyVar("   ")

    app._refresh_validation()

    assert "translation" not in app._validation_results


@pytest.mark.unit
def test_gui_translation_variable_updates_the_multiline_widget(tmp_path: Path) -> None:
    app = _build_valid_app(tmp_path)
    app._ui_built = True
    app.translation_var = DummyVar("Olá\nmundo")
    widget = EditableText()
    app.view.translation_text = widget  # type: ignore[assignment]

    app._on_translation_text_changed()

    assert widget.text == "Olá\nmundo"
    assert app._validation_results["translation"].is_valid is True


@pytest.mark.unit
def test_enable_high_dpi_is_a_no_op_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("poliglota.gui_app.sys.platform", "linux")

    assert enable_high_dpi() is False


@pytest.mark.unit
def test_enable_high_dpi_uses_the_shcore_api(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeShcore:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def SetProcessDpiAwareness(self, value: int) -> None:  # noqa: N802
            self.calls.append(value)

    shcore = FakeShcore()
    monkeypatch.setattr("poliglota.gui_app.sys.platform", "win32")
    monkeypatch.setattr(
        "poliglota.gui_app.ctypes",
        SimpleNamespace(windll=SimpleNamespace(shcore=shcore)),
    )

    assert enable_high_dpi() is True
    assert shcore.calls == [1]


@pytest.mark.unit
def test_enable_high_dpi_falls_back_to_user32(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenShcore:
        def SetProcessDpiAwareness(self, _value: int) -> None:  # noqa: N802
            msg = "already aware"
            raise OSError(msg)

    class FakeUser32:
        def __init__(self) -> None:
            self.called = False

        def SetProcessDPIAware(self) -> None:  # noqa: N802
            self.called = True

    user32 = FakeUser32()
    monkeypatch.setattr("poliglota.gui_app.sys.platform", "win32")
    monkeypatch.setattr(
        "poliglota.gui_app.ctypes",
        SimpleNamespace(windll=SimpleNamespace(shcore=BrokenShcore(), user32=user32)),
    )

    assert enable_high_dpi() is True
    assert user32.called is True


@pytest.mark.unit
def test_enable_high_dpi_tolerates_a_missing_windll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("poliglota.gui_app.sys.platform", "win32")
    monkeypatch.setattr("poliglota.gui_app.ctypes", SimpleNamespace())

    assert enable_high_dpi() is False
