"""Minimal Tkinter GUI for the Poliglota desktop workflow."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from tkinter import ttk

try:
    import tkinter as tk
except ImportError as exc:  # pragma: no cover - platform-specific fallback
    msg = "Tkinter is required for the Poliglota GUI."
    raise RuntimeError(msg) from exc

from . import __version__
from .cli import main as cli_main


class PoliglotaGUI:
    """Thin GUI wrapper around the existing Poliglota CLI logic."""

    def __init__(
        self, *, project_root: str | Path | None = None, headless: bool = False
    ) -> None:
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
        self.engine_var: tk.StringVar | None = None
        self.device_var: tk.StringVar | None = None
        self.model_var: tk.StringVar | None = None
        self._is_running = False

    def _set_status(self, message: str) -> None:
        if self.root is not None and self.status_var is not None:
            self.status_var.set(message)

    def _append_output(self, text: str) -> None:
        if self.output_text is not None:
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)

    def _show_result(self, output: str) -> None:
        if self.output_text is not None:
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, output.strip() or "Nenhuma saída do comando.")
            self.output_text.see(tk.END)

    def _run_cli_command(self, *argv: str) -> int:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = cli_main(list(argv))
        result = buffer.getvalue().strip() or f"Comando concluído com código de saída {exit_code}."
        self._show_result(result)
        self._set_status(f"Comando concluído com código {exit_code}.")
        return exit_code

    def _handle_validate(self) -> None:
        self._is_running = True
        self._set_status("Validando recursos...")
        try:
            root_value = (
                self.project_var.get().strip()
                if self.project_var is not None
                else str(self.project_root)
            )
            format_value = self.format_var.get() if self.format_var is not None else "arb"
            source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
            command = [
                "validate",
                "--root",
                str(Path(root_value) if root_value else self.project_root),
                "--source",
                source_value,
                "--format",
                format_value,
            ]
            self._run_cli_command(*command)
        finally:
            self._is_running = False

    def _handle_sync(self) -> None:
        self._is_running = True
        self._set_status("Sincronizando recursos...")
        try:
            root_value = (
                self.project_var.get().strip()
                if self.project_var is not None
                else str(self.project_root)
            )
            format_value = self.format_var.get() if self.format_var is not None else "arb"
            source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
            command = [
                "sync",
                "--root",
                str(Path(root_value) if root_value else self.project_root),
                "--source",
                source_value,
                "--dry-run",
                "--format",
                format_value,
            ]
            self._run_cli_command(*command)
        finally:
            self._is_running = False

    def _handle_list_locales(self) -> None:
        self._is_running = True
        self._set_status("Listando idiomas disponíveis...")
        try:
            root_value = (
                self.project_var.get().strip()
                if self.project_var is not None
                else str(self.project_root)
            )
            format_value = self.format_var.get() if self.format_var is not None else "arb"
            command = [
                "list-locales",
                "--root",
                str(Path(root_value) if root_value else self.project_root),
                "--format",
                format_value,
            ]
            self._run_cli_command(*command)
        finally:
            self._is_running = False

    def _handle_translate(self) -> None:
        self._is_running = True
        self._set_status("Executando tradução local...")
        try:
            text = "Olá, mundo!"
            source_value = self.source_var.get().strip() if self.source_var is not None else "pt_BR"
            target_value = self.target_var.get().strip() if self.target_var is not None else "en_US"
            engine_value = (
                self.engine_var.get().strip() if self.engine_var is not None else "marian"
            )
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
            self._run_cli_command(*command)
        finally:
            self._is_running = False

    def _build_ui(self) -> None:
        if self.headless:
            return

        self.root = tk.Tk()
        self.root.title(f"Poliglota {__version__}")
        self.root.geometry("960x640")
        self.root.minsize(760, 500)

        self.status_var = tk.StringVar(value="Pronto para validar ou sincronizar arquivos.")
        self.project_var = tk.StringVar(value=str(self.project_root))
        self.format_var = tk.StringVar(value="arb")
        self.source_var = tk.StringVar(value="pt_BR")
        self.target_var = tk.StringVar(value="en_US")
        self.engine_var = tk.StringVar(value="marian")
        self.device_var = tk.StringVar(value="auto")
        self.model_var = tk.StringVar(value="")

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
        ttk.Button(form, text="Selecionar", command=self._choose_project_dir).grid(
            row=0, column=2, pady=4
        )

        ttk.Label(form, text="Formato:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            form,
            textvariable=self.format_var,
            values=["arb", "json", "yaml", "xml"],
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(form, text="Origem:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.source_var).grid(
            row=2, column=1, sticky="ew", padx=(0, 8), pady=4
        )

        ttk.Label(form, text="Destino:").grid(row=2, column=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.target_var).grid(
            row=2, column=3, sticky="ew", padx=(0, 8), pady=4
        )

        ttk.Label(form, text="Motor:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            form,
            textvariable=self.engine_var,
            values=["marian", "pytorch"],
            state="readonly",
            width=12,
        ).grid(row=3, column=1, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(form, text="Dispositivo:").grid(row=3, column=2, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            form,
            textvariable=self.device_var,
            values=["auto", "cpu", "cuda", "mps", "gpu"],
            state="readonly",
            width=12,
        ).grid(row=3, column=3, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(form, text="Modelo:").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.model_var).grid(
            row=4, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4
        )

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        actions = ttk.Frame(main_frame)
        actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(actions, text="Validar", command=self._handle_validate).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(actions, text="Sincronizar", command=self._handle_sync).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(
            actions,
            text="Listar idiomas",
            command=self._handle_list_locales,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Traduzir", command=self._handle_translate).pack(
            side=tk.LEFT, padx=(0, 8)
        )

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

    def _choose_project_dir(self) -> None:
        if self.root is None:
            return
        selected = tk.filedialog.askdirectory(title="Selecione a pasta do projeto")
        if selected:
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
