"""Tkinter GUI for the Poliglota desktop workflow.

This module owns the behaviour of the window: validation, command building,
subprocess execution and state persistence. Everything visual (widgets, themes,
progress bar, output pane, geometry and shortcuts) lives in
:mod:`poliglota.gui_view`.
"""

from __future__ import annotations

import contextlib
import ctypes
import logging
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    import tkinter as tk
except ImportError as exc:  # pragma: no cover - platform-specific fallback
    msg = "Tkinter is required for the Poliglota GUI."
    raise RuntimeError(msg) from exc

from . import __version__
from .gui_config import (
    DEFAULT_THEME,
    THEME_CHOICES,
    GuiState,
    default_state_path,
    load_state,
    save_state,
)
from .gui_errors import build_error_report, categorize_error
from .gui_validators import (
    ValidationResult,
    validate_locale,
    validate_model_name,
    validate_project_path,
    validate_translation_text,
)
from .gui_view import (
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    GuiActions,
    GuiVariables,
    GuiView,
    configure_dpi_scaling,
)

logger = logging.getLogger(__name__)

#: Human-readable names used when reporting which field needs attention.
FIELD_LABELS: dict[str, str] = {
    "project": "Projeto",
    "source": "Idioma de origem",
    "target": "Idioma de destino",
    "model": "Modelo",
    "translation": "Texto",
}

#: Fields each GUI command actually consumes, so validation never blocks
#: a command because of a field it does not use (e.g. translating a single
#: text does not read the project folder).
COMMAND_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "validate": ("project", "source"),
    "sync": ("project", "source"),
    "list-locales": ("project",),
    "translate": ("source", "target", "model"),
    "translate-project": ("project", "source", "target", "model"),
}

#: Maximum time (seconds) a CLI command may run before being killed.
COMMAND_TIMEOUT_SECONDS = 300

#: How often (ms) the status line refreshes the running operation's elapsed time.
ELAPSED_INTERVAL_MS = 200

#: Default file name offered by the "Salvar" button.
DEFAULT_OUTPUT_FILE_NAME = "poliglota-saida.txt"


def _apply_windows_dpi_awareness() -> bool:
    """Enable DPI awareness through the Windows API, when available."""
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return False

    shcore = getattr(windll, "shcore", None)
    if shcore is not None:
        try:
            shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        else:
            return True

    user32 = getattr(windll, "user32", None)
    if user32 is None:
        return False
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        return False
    return True


def enable_high_dpi() -> bool:
    """Make the process DPI-aware on Windows, returning whether it worked."""
    if sys.platform != "win32":
        return False
    return _apply_windows_dpi_awareness()


class PoliglotaGUI:
    """Thin GUI wrapper around the existing Poliglota CLI logic."""

    #: Debounce delay (ms) before the form state is written to disk.
    STATE_SAVE_DELAY_MS = 600

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        headless: bool = False,
        state_path: str | Path | None = None,
    ) -> None:
        """Create a GUI app bound to a project root and startup mode."""
        self.view = GuiView()
        self._explicit_project_root = project_root is not None
        self.project_root = (
            Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
        )
        self.headless = headless
        self.state_path = Path(state_path) if state_path is not None else default_state_path()
        self.state = GuiState()
        self._root: tk.Tk | None = None
        self.status_var: tk.StringVar | None = None
        self.validation_var: tk.StringVar | None = None
        self.project_var: tk.StringVar | None = None
        self.format_var: tk.StringVar | None = None
        self.source_var: tk.StringVar | None = None
        self.target_var: tk.StringVar | None = None
        self.translation_var: tk.StringVar | None = None
        self.engine_var: tk.StringVar | None = None
        self.device_var: tk.StringVar | None = None
        self.model_var: tk.StringVar | None = None
        self.sync_dry_run_var: tk.BooleanVar | None = None
        self.theme_var: tk.StringVar | None = None
        self._is_running = False
        self._ui_built = False
        self._validation_results: dict[str, ValidationResult] = {}
        self._interactive_widgets: list[object] = []
        self._action_buttons: list[object] = []
        self._disabled_states: dict[int, str] = {}
        self._worker_thread: threading.Thread | None = None
        self._message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._window_closed = False
        self._poll_after_id: object | None = None
        self._save_after_id: object | None = None
        self._process: subprocess.Popen[str] | None = None
        self._cancel_requested = False
        self._streamed_output = False
        self._elapsed_token = 0
        self._operation_started = 0.0
        self._operation_message = ""

    @property
    def root(self) -> tk.Tk | None:
        """Return the Tk root window, or ``None`` when the UI is not built."""
        return self._root

    @root.setter
    def root(self, value: tk.Tk | None) -> None:
        """Keep the presentation layer pointed at the same root window."""
        self._root = value
        self.view.root = value

    @property
    def output_text(self) -> tk.Text | None:
        """Return the output pane widget owned by the view."""
        return self.view.output_text

    @output_text.setter
    def output_text(self, value: tk.Text | None) -> None:
        """Replace the output pane widget (used by tests and by the view)."""
        self.view.output_text = value

    @property
    def validation_label(self) -> ttk.Label | None:
        """Return the inline validation label owned by the view."""
        return self.view.validation_label

    @validation_label.setter
    def validation_label(self, value: ttk.Label | None) -> None:
        """Replace the inline validation label widget."""
        self.view.validation_label = value

    def _is_window_alive(self) -> bool:
        if self.root is None:
            return False
        if self._window_closed:
            return False
        exists = getattr(self.root, "winfo_exists", None)
        if exists is None:
            return True
        try:
            return bool(exists())
        except (AttributeError, RuntimeError, tk.TclError):
            self._window_closed = True
            return False

    def _schedule_ui_poll(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        if self.root is None or not self._is_window_alive():
            self._window_closed = True
            return
        if self._poll_after_id is not None:
            return
        if hasattr(self.root, "after"):
            self._poll_after_id = self.root.after(25, self._process_message_queue)

    def _cancel_ui_poll(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        if self.root is None or self._poll_after_id is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self.root.after_cancel(self._poll_after_id)
        self._poll_after_id = None

    def _process_message_queue(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return
        if self.root is None or not self._is_window_alive():
            self._window_closed = True
            self._poll_after_id = None
            return

        self._poll_after_id = None
        active = False
        try:
            while True:
                try:
                    message_type, payload = self._message_queue.get_nowait()
                except queue.Empty:
                    break

                active = True
                if message_type == "callback":
                    callback, args, kwargs = payload
                    try:
                        callback(*args, **kwargs)
                    except (AttributeError, RuntimeError, tk.TclError):
                        self._window_closed = True
                        break
                elif message_type == "status":
                    message = payload
                    if self.status_var is not None:
                        try:
                            self.status_var.set(message)
                        except (AttributeError, RuntimeError, tk.TclError):
                            self._window_closed = True
                            break
                elif message_type == "line":
                    if not self._append_output(str(payload)):
                        break
                elif message_type == "result":
                    if not self._insert_output(str(payload)):
                        break
                elif message_type == "error":
                    output, exit_code = payload
                    report = build_error_report(str(output), exit_code=int(exit_code))
                    logger.warning("CLI command failed with exit code %s", exit_code)
                    if not self._insert_output(report):
                        break
                elif message_type == "cancelled":
                    if not self._append_output("[Operação cancelada pelo usuário]"):
                        break
                elif message_type == "complete":
                    status_message = str(payload)
                    self._complete_operation(status_message=status_message)
                    self._window_closed = self._window_closed or not self._is_window_alive()
        finally:
            if (
                self.root is not None
                and self._is_window_alive()
                and not self._window_closed
                and (active or self._is_running)
            ):
                self._schedule_ui_poll()

    def _set_status(self, message: str) -> None:
        if self.root is None or self.status_var is None:
            return
        if threading.current_thread() is threading.main_thread():
            if self._window_closed or not self._is_window_alive():
                return
            self.status_var.set(message)
            return
        self._message_queue.put(("status", message))

    def _insert_output(self, output: str) -> bool:
        """Replace the output pane content, returning False when the UI is gone."""
        if self.output_text is None:
            return True
        if not self.view.show_output(output):
            self._window_closed = True
            return False
        return True

    def _append_output(self, line: str) -> bool:
        """Append one streamed line to the output pane."""
        if self.output_text is None:
            return True
        if not self.view.append_output(line):
            self._window_closed = True
            return False
        return True

    def _clear_output(self) -> None:
        """Empty the output pane before a new command starts streaming."""
        if self.output_text is None:
            return
        if not self.view.clear_output():
            self._window_closed = True

    def _handle_clear_output(self) -> None:
        """Clear the output pane on the user's request."""
        self._clear_output()
        self._set_status("Saída limpa.")

    def _copy_output(self) -> None:
        """Copy the current output pane content to the clipboard."""
        content = self.view.output_content()
        if not content:
            self._set_status("Não há saída para copiar.")
            return
        root = self.root
        clear = getattr(root, "clipboard_clear", None)
        append = getattr(root, "clipboard_append", None)
        if clear is None or append is None:
            self._set_status("Área de transferência indisponível.")
            return
        try:
            clear()
            append(content)
        except (AttributeError, RuntimeError, tk.TclError):
            self._set_status("Não foi possível copiar a saída.")
            return
        self._set_status("Saída copiada para a área de transferência.")

    def _save_output(self) -> None:
        """Save the current output pane content to a user-chosen file."""
        if self.root is None or self._window_closed or not self._is_window_alive():
            return
        content = self.view.output_content()
        if not content:
            self._set_status("Não há saída para salvar.")
            return
        try:
            selected = filedialog.asksaveasfilename(
                parent=self.root,
                title="Salvar saída",
                defaultextension=".txt",
                initialfile=DEFAULT_OUTPUT_FILE_NAME,
                filetypes=(
                    ("Arquivo de texto", "*.txt"),
                    ("Todos os arquivos", "*.*"),
                ),
            )
        except (AttributeError, RuntimeError, tk.TclError):
            return
        if not selected:
            self._set_status("Salvamento cancelado.")
            return
        try:
            Path(selected).write_text(f"{content}\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save GUI output to %s: %s", selected, exc)
            self._set_status(f"Não foi possível salvar a saída: {exc}")
            return
        self._set_status(f"Saída salva em {selected}.")

    def _stream_line(self, line: str) -> None:
        """Receive one CLI output line from the worker thread."""
        self._streamed_output = True
        if self._window_closed:
            return
        if threading.current_thread() is threading.main_thread():
            self._append_output(line)
            return
        self._message_queue.put(("line", line))

    def _show_result(self, output: str) -> None:
        if self.output_text is None:
            return
        if threading.current_thread() is threading.main_thread():
            if self._window_closed or not self._is_window_alive():
                return
            self._insert_output(output)
            return
        self._message_queue.put(("result", output))

    @staticmethod
    def _widget_state(widget: object) -> str:
        """Return the current ``state`` of a widget, defaulting to normal."""
        cget = getattr(widget, "cget", None)
        if cget is None:
            return tk.NORMAL
        try:
            state = str(cget("state"))
        except (AttributeError, TypeError, tk.TclError):
            return tk.NORMAL
        return state or tk.NORMAL

    def _set_controls_enabled(self, *, enabled: bool) -> None:
        """Disable or re-enable the form widgets, restoring readonly combos."""
        widgets = [*self._interactive_widgets, *self._action_buttons]
        for widget in widgets:
            if widget is None:
                continue
            if enabled:
                state = self._disabled_states.pop(id(widget), tk.NORMAL)
            else:
                self._disabled_states.setdefault(id(widget), self._widget_state(widget))
                state = tk.DISABLED
            try:
                widget.configure(state=state)
            except (AttributeError, TypeError, tk.TclError):
                continue

    def _begin_operation(self, message: str) -> bool:
        if self._is_running:
            return False
        self._is_running = True
        self._cancel_requested = False
        self._streamed_output = False
        self._operation_started = time.monotonic()
        self._operation_message = message
        self._elapsed_token += 1
        self._set_controls_enabled(enabled=False)
        self.view.set_busy(busy=True)
        self._set_status(message)
        self._schedule_elapsed_tick(self._elapsed_token)
        return True

    def _schedule_elapsed_tick(self, token: int) -> None:
        """Schedule the next status refresh that shows elapsed time."""
        if self.root is None or not self._is_window_alive():
            return
        after = getattr(self.root, "after", None)
        if after is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            after(ELAPSED_INTERVAL_MS, lambda: self._elapsed_tick(token))

    def _elapsed_tick(self, token: int) -> None:
        """Refresh the status line with the running operation's elapsed time."""
        if token != self._elapsed_token or not self._is_running:
            return
        elapsed = max(time.monotonic() - self._operation_started, 0.0)
        self._set_status(f"{self._operation_message} ({elapsed:.1f}s)")
        self._schedule_elapsed_tick(token)

    def _complete_operation(self, *, status_message: str | None = None) -> None:
        self._is_running = False
        self._cancel_requested = False
        self._elapsed_token += 1
        self._set_controls_enabled(enabled=True)
        self.view.set_busy(busy=False)
        if status_message is not None:
            self._set_status(status_message)

    def _cancel_operation(self) -> None:
        """Ask the running CLI process to stop."""
        if not self._is_running:
            return
        self._cancel_requested = True
        self._terminate_process()
        self._set_status("Cancelando operação...")

    def _terminate_process(self) -> None:
        """Terminate the CLI process, if one is running."""
        process = self._process
        if process is None:
            return
        self._terminate(process)

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        with contextlib.suppress(OSError):
            process.terminate()

    @staticmethod
    def _handle_timeout(process: subprocess.Popen[str], timed_out: threading.Event) -> None:
        timed_out.set()
        with contextlib.suppress(OSError):
            process.kill()

    @staticmethod
    def _var_value(var: object | None) -> str:
        """Return the stripped text held by a Tk variable, or an empty string."""
        return PoliglotaGUI._raw_var_value(var).strip()

    @staticmethod
    def _raw_var_value(var: object | None) -> str:
        """Return the raw text held by a Tk variable, preserving whitespace."""
        getter = getattr(var, "get", None)
        if getter is None:
            return ""
        try:
            return str(getter())
        except (AttributeError, RuntimeError, tk.TclError):
            return ""

    def _collect_validation_results(self) -> dict[str, ValidationResult]:
        """Validate the fields that every command depends on."""
        return {
            "project": validate_project_path(self._var_value(self.project_var)),
            "source": validate_locale(
                self._var_value(self.source_var),
                label=FIELD_LABELS["source"],
            ),
            "target": validate_locale(
                self._var_value(self.target_var),
                label=FIELD_LABELS["target"],
            ),
            "model": validate_model_name(self._var_value(self.model_var)),
        }

    def _refresh_validation(self) -> None:
        """Re-run field validation, highlight invalid entries and update the label."""
        results = self._collect_validation_results()
        text_value = self._var_value(self.translation_var)
        if text_value:
            results["translation"] = validate_translation_text(text_value)
        self._validation_results = results
        invalid = [
            (name, result)
            for name, result in self._validation_results.items()
            if not result.is_valid
        ]
        self.view.mark_invalid({name for name, _ in invalid})
        if self.validation_var is None:
            return

        if invalid:
            name, result = invalid[0]
            extra = f" (+{len(invalid) - 1} outro(s) campo(s))" if len(invalid) > 1 else ""
            message = f"✗ {FIELD_LABELS.get(name, name)}: {result.message}{extra}"
        else:
            message = "✓ Configuração válida."

        try:
            self.validation_var.set(message)
        except (AttributeError, RuntimeError, tk.TclError):
            return
        self.view.show_validation_state(is_error=bool(invalid))

    def _validate_form(self, command: str = "validate") -> bool:
        """Validate only the fields the given command actually consumes."""
        self._refresh_validation()
        required = COMMAND_REQUIREMENTS.get(command, ())
        invalid = [
            name
            for name in required
            if not self._validation_results.get(name, ValidationResult.ok()).is_valid
        ]
        if not invalid:
            return True

        self._focus_first_invalid(invalid[0])
        self._set_status(
            f"Corrija os campos indicados antes de continuar ({len(invalid)} pendência(s)).",
        )
        return False

    def _focus_first_invalid(self, name: str) -> None:
        """Move keyboard focus to the first invalid field, when possible."""
        self.view.focus_field(name)

    def _on_form_changed(self, *_args: object) -> None:
        """React to a field change: refresh validation and queue a state save."""
        self._refresh_validation()
        self._schedule_state_save()

    def _on_translation_text_changed(self, *_args: object) -> None:
        """Mirror the text variable into the multiline widget and revalidate."""
        if not self._ui_built:
            return
        self.view.set_translation_text(self._raw_var_value(self.translation_var))
        self._refresh_validation()

    def _on_theme_changed(self, *_args: object) -> None:
        """Apply the selected theme and remember the choice."""
        if not self._ui_built:
            return
        name = self._var_value(self.theme_var) or DEFAULT_THEME
        applied = self.view.apply_theme(name)
        if applied != name and self.theme_var is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                self.theme_var.set(applied)
        self._schedule_state_save()

    def _cancel_state_save(self) -> None:
        """Cancel a pending debounced state save."""
        if self.root is None or self._save_after_id is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = None

    def _schedule_state_save(self) -> None:
        """Persist the form state shortly after the user stops typing."""
        if not self._ui_built or self.root is None or self._window_closed:
            return
        if not self._is_window_alive():
            return
        self._cancel_state_save()
        if hasattr(self.root, "after"):
            self._save_after_id = self.root.after(self.STATE_SAVE_DELAY_MS, self._save_state_now)

    def _current_state(self) -> GuiState:
        """Build a GuiState snapshot from the current widget values."""
        dry_run = self.sync_dry_run_var.get() if self.sync_dry_run_var is not None else True
        theme = self._var_value(self.theme_var) or self.view.theme
        if theme not in THEME_CHOICES:
            theme = DEFAULT_THEME
        return GuiState(
            project_root=self._var_value(self.project_var) or str(self.project_root),
            format=self._var_value(self.format_var) or "arb",
            source_locale=self._var_value(self.source_var) or "pt_BR",
            target_locale=self._var_value(self.target_var) or "en_US",
            engine=self._var_value(self.engine_var) or "marian",
            device=self._var_value(self.device_var) or "auto",
            model_name=self._var_value(self.model_var),
            dry_run=bool(dry_run),
            theme=theme,
            window_geometry=self.view.geometry() or self.state.window_geometry,
        )

    def _save_state_now(self) -> None:
        """Write the current form state to disk immediately."""
        self._save_after_id = None
        if not self._ui_built:
            return
        self.state = self._current_state()
        save_state(self.state, self.state_path)

    def _build_project_root(self) -> Path:
        raw_value = self.project_var.get().strip() if self.project_var is not None else ""
        if not raw_value:
            return self.project_root
        return Path(raw_value)

    def _build_translate_command(self) -> list[str]:
        if self.translation_var is None:
            msg = "Informe o texto para tradução."
            raise ValueError(msg)

        text = self.translation_var.get().strip()
        if not text:
            msg = "Informe o texto para tradução."
            raise ValueError(msg)

        source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
        target_value = self.target_var.get().strip() if self.target_var is not None else "en_US"
        engine_value = self.engine_var.get().strip() if self.engine_var is not None else "marian"
        device_value = self.device_var.get().strip() if self.device_var is not None else "auto"
        model_value = self.model_var.get().strip() if self.model_var is not None else ""

        command = [
            "translate",
            text,
            "--source",
            source_value,
            "--target",
            target_value,
            "--engine",
            engine_value,
            "--device",
            device_value,
        ]
        if model_value:
            command.extend(["--model", model_value])
        return command

    def _build_sync_command(self) -> list[str]:
        root_value = self._build_project_root()
        source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
        format_value = self.format_var.get() if self.format_var is not None else "arb"
        dry_run = self.sync_dry_run_var.get() if self.sync_dry_run_var is not None else True

        command = [
            "sync",
            "--root",
            str(root_value),
            "--source",
            source_value,
        ]
        if dry_run:
            command.append("--dry-run")
        command.extend(["--format", format_value])
        return command

    def _run_cli_command(
        self,
        *argv: str,
        on_line: Callable[[str], None] | None = None,
    ) -> tuple[int, str]:
        """Run the CLI, streaming each output line through ``on_line``."""
        command = [sys.executable, "-m", "poliglota", *argv]
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            return 1, f"Erro ao executar o comando: {exc}"

        self._process = process
        if self._cancel_requested:
            self._terminate(process)
        timed_out = threading.Event()
        timer = threading.Timer(
            COMMAND_TIMEOUT_SECONDS,
            self._handle_timeout,
            args=(process, timed_out),
        )
        timer.daemon = True
        timer.start()

        lines: list[str] = []
        stream = process.stdout
        try:
            if stream is not None:
                for raw_line in stream:
                    line = raw_line.rstrip("\r\n")
                    if not line:
                        continue
                    lines.append(line)
                    if on_line is not None:
                        on_line(line)
                    if self._cancel_requested and process.poll() is None:
                        self._terminate(process)
            returncode = process.wait()
        finally:
            timer.cancel()
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()
            self._process = None

        if timed_out.is_set():
            return 1, "Tempo limite excedido ao executar o comando."

        output = "\n".join(lines).strip()
        if not output:
            output = f"Comando concluído com código de saída {returncode}."
        return returncode, output

    def _dispatch_command(
        self,
        command: list[str],
        *,
        busy_message: str,
        success_message: str,
    ) -> None:
        if self._window_closed or not self._is_window_alive():
            return
        if not self._begin_operation(busy_message):
            return
        logger.info("Dispatching CLI command: %s", " ".join(command))
        self._clear_output()
        self._schedule_ui_poll()

        def worker() -> None:
            try:
                exit_code, output = self._run_cli_command(*command, on_line=self._stream_line)
            except OSError as exc:
                output = f"Erro ao executar comando: {exc}"
                exit_code = 1

            if self._cancel_requested:
                logger.info("CLI command cancelled by the user")
                self._message_queue.put(("cancelled", None))
                self._message_queue.put(("status", "Operação cancelada."))
                self._message_queue.put(("complete", "Operação cancelada."))
            elif exit_code == 0:
                if not self._streamed_output:
                    self._message_queue.put(("result", output))
                self._message_queue.put(("status", success_message))
                self._message_queue.put(("complete", success_message))
            else:
                category = categorize_error(output)
                failure = f"Erro: {category.title}"
                logger.warning("CLI command failed (%s): %s", exit_code, category.code)
                self._message_queue.put(("error", (output, exit_code)))
                self._message_queue.put(("status", failure))
                self._message_queue.put(("complete", failure))
            self._schedule_ui_poll()

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _handle_validate(self) -> None:
        if not self._validate_form("validate"):
            return
        root_value = self.project_root if self.project_var is None else self._build_project_root()
        format_value = self.format_var.get() if self.format_var is not None else "arb"
        source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
        command = [
            "validate",
            "--root",
            str(root_value),
            "--source",
            source_value,
            "--format",
            format_value,
        ]
        self._dispatch_command(
            command,
            busy_message="Validando recursos...",
            success_message="Validação concluída.",
        )

    def _handle_sync(self) -> None:
        if not self._validate_form("sync"):
            return
        command = self._build_sync_command()
        self._dispatch_command(
            command,
            busy_message="Sincronizando recursos...",
            success_message="Sincronização concluída.",
        )

    def _handle_list_locales(self) -> None:
        if not self._validate_form("list-locales"):
            return
        root_value = self.project_root if self.project_var is None else self._build_project_root()
        format_value = self.format_var.get() if self.format_var is not None else "arb"
        command = [
            "list-locales",
            "--root",
            str(root_value),
            "--format",
            format_value,
        ]
        self._dispatch_command(
            command,
            busy_message="Listando idiomas disponíveis...",
            success_message="Listagem concluída.",
        )

    def _handle_translate(self) -> None:
        if not self._validate_form("translate"):
            return

        text_result = validate_translation_text(self._var_value(self.translation_var))
        if not text_result.is_valid:
            self._show_result(text_result.message)
            self._set_status(text_result.message)
            return

        try:
            command = self._build_translate_command()
        except ValueError as exc:
            self._show_result(str(exc))
            self._set_status(str(exc))
            return

        self._dispatch_command(
            command,
            busy_message="Executando tradução local...",
            success_message="Tradução concluída.",
        )

    def _build_translate_project_command(self) -> list[str]:
        root_value = self._build_project_root()
        source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
        target_value = self.target_var.get().strip() if self.target_var is not None else "en_US"
        engine_value = self.engine_var.get().strip() if self.engine_var is not None else "marian"
        device_value = self.device_var.get().strip() if self.device_var is not None else "auto"
        model_value = self.model_var.get().strip() if self.model_var is not None else ""
        format_value = self.format_var.get() if self.format_var is not None else "arb"

        command = [
            "translate-project",
            "--root",
            str(root_value),
            "--source",
            source_value,
            "--target",
            target_value,
            "--engine",
            engine_value,
            "--device",
            device_value,
            "--format",
            format_value,
        ]
        if model_value:
            command.extend(["--model", model_value])
        return command

    def _handle_translate_project(self) -> None:
        if not self._validate_form("translate-project"):
            return
        try:
            command = self._build_translate_project_command()
        except ValueError as exc:
            self._show_result(str(exc))
            self._set_status(str(exc))
            return

        self._dispatch_command(
            command,
            busy_message="Traduzindo projeto completo...",
            success_message="Traducao do projeto concluida.",
        )

    def _build_ui(self) -> None:
        if self.headless:
            return

        enable_high_dpi()
        self.root = tk.Tk()
        self.root.title(f"Poliglota {__version__}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self._close_window)
        configure_dpi_scaling(self.root)

        self.state = load_state(self.state_path)
        if not self._explicit_project_root and self.state.project_root:
            self.project_root = Path(self.state.project_root).expanduser()

        self.status_var = tk.StringVar(value="Pronto para validar ou sincronizar arquivos.")
        self.validation_var = tk.StringVar(value="")
        self.project_var = tk.StringVar(value=self.state.project_root or str(self.project_root))
        self.format_var = tk.StringVar(value=self.state.format)
        self.source_var = tk.StringVar(value=self.state.source_locale)
        self.target_var = tk.StringVar(value=self.state.target_locale)
        self.translation_var = tk.StringVar(value="")
        self.engine_var = tk.StringVar(value=self.state.engine)
        self.device_var = tk.StringVar(value=self.state.device)
        self.model_var = tk.StringVar(value=self.state.model_name)
        self.sync_dry_run_var = tk.BooleanVar(value=self.state.dry_run)
        theme_name = self.state.theme if self.state.theme in THEME_CHOICES else DEFAULT_THEME
        self.theme_var = tk.StringVar(value=theme_name)
        self._interactive_widgets = []
        self._action_buttons = []
        self._disabled_states = {}
        self._ui_built = False

        variables = GuiVariables(
            status=self.status_var,
            validation=self.validation_var,
            project=self.project_var,
            format=self.format_var,
            source=self.source_var,
            target=self.target_var,
            translation=self.translation_var,
            engine=self.engine_var,
            device=self.device_var,
            model=self.model_var,
            dry_run=self.sync_dry_run_var,
            theme=self.theme_var,
        )
        actions = GuiActions(
            validate=self._handle_validate,
            sync=self._handle_sync,
            list_locales=self._handle_list_locales,
            translate=self._handle_translate,
            translate_project=self._handle_translate_project,
            choose_project=self._choose_project_dir,
            cancel=self._cancel_operation,
            restore_defaults=self._restore_defaults,
            copy_output=self._copy_output,
            save_output=self._save_output,
            clear_output=self._handle_clear_output,
        )

        self.view.build(
            root=self.root,
            variables=variables,
            actions=actions,
            version=__version__,
        )
        self._interactive_widgets = self.view.interactive_widgets
        self._action_buttons = self.view.action_buttons
        self.view.apply_theme(theme_name)
        self.view.apply_geometry(self.state.window_geometry)
        self.view.bind_shortcuts()

        for variable in (
            self.project_var,
            self.format_var,
            self.source_var,
            self.target_var,
            self.engine_var,
            self.device_var,
            self.model_var,
            self.sync_dry_run_var,
        ):
            variable.trace_add("write", self._on_form_changed)
        self.theme_var.trace_add("write", self._on_theme_changed)
        self.translation_var.trace_add("write", self._on_translation_text_changed)

        self._ui_built = True
        self._refresh_validation()

    def _restore_defaults(self) -> None:
        """Reset the form to the built-in defaults, keeping the current theme."""
        defaults = GuiState()
        theme = self._var_value(self.theme_var) or self.view.theme
        values = (
            (self.project_var, str(self.project_root)),
            (self.format_var, defaults.format),
            (self.source_var, defaults.source_locale),
            (self.target_var, defaults.target_locale),
            (self.engine_var, defaults.engine),
            (self.device_var, defaults.device),
            (self.model_var, defaults.model_name),
            (self.sync_dry_run_var, defaults.dry_run),
            (self.translation_var, ""),
            (self.theme_var, theme),
        )
        for variable, value in values:
            if variable is None:
                continue
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                variable.set(value)
        self._refresh_validation()
        self._schedule_state_save()
        self._set_status("Padrões restaurados.")

    def _confirm_close(self) -> bool:
        """Ask the user before closing the window during a running operation."""
        ask = getattr(messagebox, "askyesno", None)
        if ask is None:
            return True
        try:
            return bool(
                ask(
                    "Poliglota",
                    "Uma operação está em andamento. Deseja realmente fechar a janela?",
                ),
            )
        except (AttributeError, RuntimeError, tk.TclError):
            return True

    def _close_window(self) -> None:
        if self._is_running and not self._confirm_close():
            return
        self._cancel_state_save()
        self._cancel_requested = True
        self._terminate_process()
        self._save_state_now()
        self._window_closed = True
        self._cancel_ui_poll()
        if self.root is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                self.root.destroy()

    def _choose_project_dir(self) -> None:
        if self.root is None or self._window_closed or not self._is_window_alive():
            return
        selected = filedialog.askdirectory(title="Selecione a pasta do projeto")
        if selected and self.project_var is not None:
            self.project_var.set(selected)

    def run(self) -> int:
        """Open the GUI window and start the Tk event loop."""
        if self.headless:
            return 0
        self._build_ui()
        if self.root is not None:
            self.root.mainloop()
        return 0


def build_gui_app(
    *,
    project_root: str | Path | None = None,
    headless: bool = False,
    state_path: str | Path | None = None,
) -> PoliglotaGUI:
    """Create a GUI app instance for CLI or test use."""
    return PoliglotaGUI(project_root=project_root, headless=headless, state_path=state_path)
