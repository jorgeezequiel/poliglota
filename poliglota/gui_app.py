"""Minimal Tkinter GUI for the Poliglota desktop workflow."""

from __future__ import annotations

import contextlib
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    import tkinter as tk
except ImportError as exc:  # pragma: no cover - platform-specific fallback
    msg = "Tkinter is required for the Poliglota GUI."
    raise RuntimeError(msg) from exc

from . import __version__


class PoliglotaGUI:
    """Thin GUI wrapper around the existing Poliglota CLI logic."""

    def __init__(self, *, project_root: str | Path | None = None, headless: bool = False) -> None:
        """Create a GUI app bound to a project root and startup mode."""
        self.project_root = (
            Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
        )
        self.headless = headless
        self.root: tk.Tk | None = None
        self.status_var: tk.StringVar | None = None
        self.output_text: tk.Text | None = None
        self.project_var: tk.StringVar | None = None
        self.format_var: tk.StringVar | None = None
        self.source_var: tk.StringVar | None = None
        self.target_var: tk.StringVar | None = None
        self.translation_var: tk.StringVar | None = None
        self.engine_var: tk.StringVar | None = None
        self.device_var: tk.StringVar | None = None
        self.model_var: tk.StringVar | None = None
        self.sync_dry_run_var: tk.BooleanVar | None = None
        self._is_running = False
        self._interactive_widgets: list[object] = []
        self._action_buttons: list[object] = []
        self._worker_thread: threading.Thread | None = None
        self._message_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._window_closed = False
        self._poll_after_id: object | None = None

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

    def _queue_ui_update(
        self,
        callback: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> None:
        if self._window_closed or not self._is_window_alive():
            return
        if threading.current_thread() is threading.main_thread():
            callback(*args, **kwargs)
            return
        self._message_queue.put(("callback", (callback, args, kwargs)))

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
                elif message_type == "result":
                    output = payload
                    if self.output_text is not None:
                        try:
                            self.output_text.delete("1.0", tk.END)
                            self.output_text.insert(
                                tk.END,
                                output.strip() or "Nenhuma saída do comando.",
                            )
                            self.output_text.see(tk.END)
                        except (AttributeError, RuntimeError, tk.TclError):
                            self._window_closed = True
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

    def _show_result(self, output: str) -> None:
        if self.output_text is None:
            return
        if threading.current_thread() is threading.main_thread():
            if self._window_closed or not self._is_window_alive():
                return
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, output.strip() or "Nenhuma saída do comando.")
            self.output_text.see(tk.END)
            return
        self._message_queue.put(("result", output))

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in self._interactive_widgets:
            if widget is None:
                continue
            try:
                widget.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except (AttributeError, TypeError, tk.TclError):
                continue
        for button in self._action_buttons:
            if button is None:
                continue
            try:
                button.configure(state=tk.NORMAL if enabled else tk.DISABLED)
            except (AttributeError, TypeError, tk.TclError):
                continue

    def _begin_operation(self, message: str) -> bool:
        if self._is_running:
            return False
        self._is_running = True
        self._set_controls_enabled(enabled=False)
        self._set_status(message)
        return True

    def _complete_operation(self, *, status_message: str | None = None) -> None:
        self._is_running = False
        self._set_controls_enabled(enabled=True)
        if status_message is not None:
            self._set_status(status_message)

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

    def _run_cli_command(self, *argv: str) -> tuple[int, str]:
        try:
            completed = subprocess.run(  # noqa: S603
                [sys.executable, "-m", "poliglota", *argv],
                capture_output=True,
                cwd=str(self.project_root),
                text=True,
                check=False,
                timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, f"Erro ao executar o comando: {exc}"

        if completed.returncode != 0 and completed.stderr.strip():
            output = completed.stderr.strip()
        else:
            output = completed.stdout.strip() or completed.stderr.strip()

        if not output:
            output = f"Comando concluído com código de saída {completed.returncode}."
        return completed.returncode, output

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
        self._schedule_ui_poll()

        def worker() -> None:
            try:
                exit_code, output = self._run_cli_command(*command)
            except OSError as exc:
                output = f"Erro ao executar comando: {exc}"
                exit_code = 1

            status = success_message if exit_code == 0 else f"Erro: código {exit_code}."
            self._message_queue.put(("result", output))
            self._message_queue.put(("status", status))
            self._message_queue.put(("complete", status))
            self._schedule_ui_poll()

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _handle_validate(self) -> None:
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
        command = self._build_sync_command()
        self._dispatch_command(
            command,
            busy_message="Sincronizando recursos...",
            success_message="Sincronização concluída.",
        )

    def _handle_list_locales(self) -> None:
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

    def _build_ui(self) -> None:
        if self.headless:
            return

        self.root = tk.Tk()
        self.root.title(f"Poliglota {__version__}")
        self.root.geometry("960x640")
        self.root.minsize(760, 500)
        self.root.protocol("WM_DELETE_WINDOW", self._close_window)

        self.status_var = tk.StringVar(value="Pronto para validar ou sincronizar arquivos.")
        self.project_var = tk.StringVar(value=str(self.project_root))
        self.format_var = tk.StringVar(value="arb")
        self.source_var = tk.StringVar(value="pt_BR")
        self.target_var = tk.StringVar(value="en_US")
        self.translation_var = tk.StringVar(value="")
        self.engine_var = tk.StringVar(value="marian")
        self.device_var = tk.StringVar(value="auto")
        self.model_var = tk.StringVar(value="")
        self.sync_dry_run_var = tk.BooleanVar(value=True)
        self._interactive_widgets = []
        self._action_buttons = []

        main_frame = ttk.Frame(self.root, padding=14)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            main_frame,
            text="Poliglota — GUI desktop",
            font=("Segoe UI", 14, "bold"),
        )
        header.pack(anchor="w", pady=(0, 8))

        ttk.Label(main_frame, text=f"Versão: {__version__}").pack(anchor="w")
        ttk.Label(
            main_frame,
            text=(
                "A CLI continua sendo a interface oficial; "
                "esta GUI apenas reutiliza a mesma lógica."
            ),
        ).pack(anchor="w", pady=(0, 6))

        form = ttk.Frame(main_frame)
        form.pack(fill=tk.X, pady=(8, 12))

        ttk.Label(form, text="Projeto:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        project_entry = ttk.Entry(form, textvariable=self.project_var)
        project_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._interactive_widgets.append(project_entry)
        select_button = ttk.Button(form, text="Selecionar", command=self._choose_project_dir)
        select_button.grid(row=0, column=2, pady=4)
        self._action_buttons.append(select_button)

        ttk.Label(form, text="Formato:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        format_combo = ttk.Combobox(
            form,
            textvariable=self.format_var,
            values=["arb", "json", "yaml", "xml"],
            state="readonly",
            width=12,
        )
        format_combo.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)
        self._interactive_widgets.append(format_combo)

        ttk.Label(form, text="Origem:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        source_entry = ttk.Entry(form, textvariable=self.source_var)
        source_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._interactive_widgets.append(source_entry)

        ttk.Label(form, text="Destino:").grid(row=2, column=2, sticky="w", padx=(0, 8), pady=4)
        target_entry = ttk.Entry(form, textvariable=self.target_var)
        target_entry.grid(row=2, column=3, sticky="ew", padx=(0, 8), pady=4)
        self._interactive_widgets.append(target_entry)

        ttk.Label(form, text="Texto:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        text_entry = ttk.Entry(form, textvariable=self.translation_var)
        text_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4)
        self._interactive_widgets.append(text_entry)

        ttk.Label(form, text="Motor:").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        engine_combo = ttk.Combobox(
            form,
            textvariable=self.engine_var,
            values=["marian", "pytorch"],
            state="readonly",
            width=12,
        )
        engine_combo.grid(row=4, column=1, sticky="w", padx=(0, 8), pady=4)
        self._interactive_widgets.append(engine_combo)

        ttk.Label(form, text="Dispositivo:").grid(row=4, column=2, sticky="w", padx=(0, 8), pady=4)
        device_combo = ttk.Combobox(
            form,
            textvariable=self.device_var,
            values=["auto", "cpu", "cuda", "mps", "gpu"],
            state="readonly",
            width=12,
        )
        device_combo.grid(row=4, column=3, sticky="w", padx=(0, 8), pady=4)
        self._interactive_widgets.append(device_combo)

        ttk.Label(form, text="Modelo:").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        model_entry = ttk.Entry(form, textvariable=self.model_var)
        model_entry.grid(row=5, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4)
        self._interactive_widgets.append(model_entry)

        sync_toggle = ttk.Checkbutton(
            form,
            text="Executar em modo dry-run",
            variable=self.sync_dry_run_var,
        )
        sync_toggle.grid(row=6, column=0, columnspan=4, sticky="w", padx=(0, 8), pady=(4, 0))
        self._interactive_widgets.append(sync_toggle)

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        actions = ttk.Frame(main_frame)
        actions.pack(fill=tk.X, pady=(0, 12))

        validate_button = ttk.Button(actions, text="Validar", command=self._handle_validate)
        validate_button.pack(side=tk.LEFT, padx=(0, 8))
        self._action_buttons.append(validate_button)

        sync_button = ttk.Button(actions, text="Sincronizar", command=self._handle_sync)
        sync_button.pack(side=tk.LEFT, padx=(0, 8))
        self._action_buttons.append(sync_button)

        locales_button = ttk.Button(
            actions,
            text="Listar idiomas",
            command=self._handle_list_locales,
        )
        locales_button.pack(side=tk.LEFT, padx=(0, 8))
        self._action_buttons.append(locales_button)

        translate_button = ttk.Button(actions, text="Traduzir", command=self._handle_translate)
        translate_button.pack(side=tk.LEFT, padx=(0, 8))
        self._action_buttons.append(translate_button)

        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor="w", pady=(0, 8))

        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(output_frame, width=120, height=18, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.insert(
            tk.END,
            "Poliglota pronto. Use a CLI ou a GUI para validar, "
            "sincronizar e traduzir recursos locais.\n",
        )

    def _close_window(self) -> None:
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
    *, project_root: str | Path | None = None, headless: bool = False
) -> PoliglotaGUI:
    """Create a GUI app instance for CLI or test use."""
    return PoliglotaGUI(project_root=project_root, headless=headless)
