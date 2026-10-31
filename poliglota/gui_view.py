"""Presentation layer of the Poliglota desktop GUI.

The window is built from plain ``ttk`` widgets, and everything visual lives
here: layout, themes, invalid-field highlighting, progress feedback, the output
pane, window geometry and keyboard shortcuts.

:class:`poliglota.gui_app.PoliglotaGUI` keeps the handlers (validation, command
building, subprocess execution and persistence) and talks to this module
through the small API below, so Tkinter code and command logic can evolve
without dragging each other along.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - platform-specific fallback
    msg = "Tkinter is required for the Poliglota GUI."
    raise RuntimeError(msg) from exc

from .gui_config import (
    DEFAULT_THEME,
    DEVICE_CHOICES,
    ENGINE_CHOICES,
    FORMAT_CHOICES,
    LOCALE_CHOICES,
    MODEL_CHOICES,
    THEME_CHOICES,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Iterator

DEFAULT_GEOMETRY = "960x640"
MIN_WINDOW_WIDTH = 760
MIN_WINDOW_HEIGHT = 500
DEFAULT_WINDOW_OFFSET = 40
MIN_VISIBLE_MARGIN = 120
PROGRESS_INTERVAL_MS = 12
TOOLTIP_DELAY_MS = 500
TOOLTIP_BACKGROUND = "#ffffe0"
TOOLTIP_FOREGROUND = "#1b1f24"
TOOLTIP_OFFSET_X = 12
TOOLTIP_OFFSET_Y = 6

GEOMETRY_PATTERN = re.compile(r"(\d{2,5})x(\d{2,5})(?:([+-]\d{1,5})([+-]\d{1,5}))?")

INVALID_ENTRY_STYLE = "Invalid.TEntry"
NORMAL_ENTRY_STYLE = "TEntry"
INVALID_COMBO_STYLE = "Invalid.TCombobox"
NORMAL_COMBO_STYLE = "TCombobox"

#: Tk tag used to paint lines that arrived on the CLI's stderr.
STDERR_TAG = "stderr"

#: Drag-and-drop payload name understood by ``tkinterdnd2``.
DND_FILES = "DND_Files"

#: Placeholder shown in the preset combobox when nothing is selected.
NO_PRESET_LABEL = "(nenhum)"


@dataclass(frozen=True, slots=True)
class Theme:
    """Colors used by one visual theme."""

    name: str
    background: str
    surface: str
    foreground: str
    muted: str
    accent: str
    accent_text: str
    error: str
    success: str
    invalid_background: str
    output_background: str
    output_foreground: str
    selection: str
    border: str


THEMES: dict[str, Theme] = {
    "light": Theme(
        name="light",
        background="#f4f6f8",
        surface="#ffffff",
        foreground="#1b1f24",
        muted="#5a6672",
        accent="#0a66c2",
        accent_text="#ffffff",
        error="#b00020",
        success="#0a7d32",
        invalid_background="#ffe3e6",
        output_background="#ffffff",
        output_foreground="#1b1f24",
        selection="#cfe3ff",
        border="#c8ced6",
    ),
    "dark": Theme(
        name="dark",
        background="#1e1f22",
        surface="#26282c",
        foreground="#e8eaed",
        muted="#9aa4b0",
        accent="#6ea8fe",
        accent_text="#10131a",
        error="#ff8a9a",
        success="#7bd88f",
        invalid_background="#4a2026",
        output_background="#17181a",
        output_foreground="#e8eaed",
        selection="#2f4f6f",
        border="#3a3f46",
    ),
}


def resolve_theme(name: str) -> Theme:
    """Return the theme registered under ``name``, falling back to the default."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def normalize_geometry(geometry: str, *, screen_width: int, screen_height: int) -> str:
    """Return a safe geometry string, clamping size and position to the screen.

    A missing, malformed or off-screen geometry falls back to the default size
    so a saved window can never reopen invisible outside the visible desktop.
    """
    match = GEOMETRY_PATTERN.fullmatch((geometry or "").strip())
    if match is None:
        return DEFAULT_GEOMETRY

    width = _clamp(int(match.group(1)), MIN_WINDOW_WIDTH, max(screen_width, MIN_WINDOW_WIDTH))
    height = _clamp(int(match.group(2)), MIN_WINDOW_HEIGHT, max(screen_height, MIN_WINDOW_HEIGHT))

    raw_x, raw_y = match.group(3), match.group(4)
    if raw_x is None or raw_y is None:
        return f"{width}x{height}"

    x = int(raw_x)
    y = int(raw_y)
    if not 0 <= x <= max(screen_width - MIN_VISIBLE_MARGIN, 0):
        x = DEFAULT_WINDOW_OFFSET
    if not 0 <= y <= max(screen_height - MIN_VISIBLE_MARGIN, 0):
        y = DEFAULT_WINDOW_OFFSET

    return f"{width}x{height}+{x}+{y}"


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def parse_drop_paths(payload: str) -> list[str]:
    """Split a Tk drop payload into individual paths.

    Tk wraps paths containing spaces in braces and separates entries with
    whitespace, so ``{C:/a b} C:/c`` yields two paths. Empty payloads and
    unbalanced braces degrade to whatever could be read.
    """
    paths: list[str] = []
    buffer: list[str] = []
    depth = 0

    for char in payload or "":
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth = max(depth - 1, 0)
            continue
        if char.isspace() and depth == 0:
            if buffer:
                paths.append("".join(buffer))
                buffer = []
            continue
        buffer.append(char)

    if buffer:
        paths.append("".join(buffer))

    return paths


def configure_dpi_scaling(root: object) -> float | None:
    """Match Tk's scaling to the monitor DPI, returning the factor applied.

    Windows reports a high-DPI monitor through ``winfo_fpixels`` only after the
    process is made DPI-aware. The scaling factor keeps fonts and paddings
    proportional instead of tiny on 125%, 150% and 200% displays.
    """
    fpixels = getattr(root, "winfo_fpixels", None)
    tk_call = getattr(root, "tk", None)
    call = getattr(tk_call, "call", None)
    if fpixels is None or call is None:
        return None

    try:
        pixels_per_inch = float(fpixels("1i"))
    except (AttributeError, TypeError, ValueError, tk.TclError):
        return None
    if pixels_per_inch <= 0:
        return None

    scaling = pixels_per_inch / 72
    with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
        call("tk", "scaling", scaling)
    return scaling


class Tooltip:
    """Small hover tooltip implemented with plain Tkinter widgets."""

    def __init__(
        self,
        widget: object,
        text: str,
        *,
        delay_ms: int = TOOLTIP_DELAY_MS,
    ) -> None:
        """Bind ``widget`` so ``text`` appears after a short hover."""
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._window: tk.Toplevel | None = None
        self._after_id: object | None = None
        self._bind()

    def _bind(self) -> None:
        bind = getattr(self.widget, "bind", None)
        if bind is None:
            return
        for sequence, handler in (
            ("<Enter>", self._schedule),
            ("<Leave>", self.hide),
            ("<ButtonPress>", self.hide),
        ):
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                bind(sequence, handler)

    def _schedule(self, _event: object = None) -> None:
        after = getattr(self.widget, "after", None)
        if after is None or self._after_id is not None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self._after_id = after(self.delay_ms, self._show)

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None:
            return
        try:
            window = tk.Toplevel(self.widget)
            window.wm_overrideredirect(boolean=True)
            window.wm_geometry(f"+{self._position_x()}+{self._position_y()}")
            tk.Label(
                window,
                text=self.text,
                background=TOOLTIP_BACKGROUND,
                foreground=TOOLTIP_FOREGROUND,
                relief=tk.SOLID,
                borderwidth=1,
                padx=6,
                pady=3,
            ).pack()
        except (AttributeError, RuntimeError, tk.TclError):
            self._window = None
            return
        self._window = window

    def _position_x(self) -> int:
        getter = getattr(self.widget, "winfo_rootx", None)
        if getter is None:
            return 0
        try:
            return int(getter()) + TOOLTIP_OFFSET_X
        except (AttributeError, TypeError, tk.TclError):
            return 0

    def _position_y(self) -> int:
        root_getter = getattr(self.widget, "winfo_rooty", None)
        height_getter = getattr(self.widget, "winfo_height", None)
        try:
            root_y = int(root_getter()) if root_getter is not None else 0
            height = int(height_getter()) if height_getter is not None else 0
        except (AttributeError, TypeError, tk.TclError):
            return 0
        return root_y + height + TOOLTIP_OFFSET_Y

    def hide(self, _event: object = None) -> None:
        """Hide the tooltip and cancel a pending appearance."""
        after_cancel = getattr(self.widget, "after_cancel", None)
        if after_cancel is not None and self._after_id is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                after_cancel(self._after_id)
        self._after_id = None
        window = self._window
        self._window = None
        if window is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                window.destroy()

    def destroy(self) -> None:
        """Remove the tooltip from the widget."""
        self.hide()


@dataclass(slots=True)
class GuiVariables:
    """Tk variables shared between the app state and the widgets."""

    status: tk.StringVar
    validation: tk.StringVar
    project: tk.StringVar
    format: tk.StringVar
    source: tk.StringVar
    target: tk.StringVar
    translation: tk.StringVar
    engine: tk.StringVar
    device: tk.StringVar
    model: tk.StringVar
    dry_run: tk.BooleanVar
    theme: tk.StringVar
    preset: tk.StringVar


@dataclass(frozen=True, slots=True)
class GuiActions:
    """Callbacks the window triggers; the app owns their implementation."""

    validate: Callable[[], None]
    sync: Callable[[], None]
    list_locales: Callable[[], None]
    translate: Callable[[], None]
    translate_project: Callable[[], None]
    choose_project: Callable[[], None]
    project_history_selected: Callable[[], None]
    cancel: Callable[[], None]
    restore_defaults: Callable[[], None]
    copy_output: Callable[[], None]
    save_output: Callable[[], None]
    clear_output: Callable[[], None]
    apply_preset: Callable[[], None]
    save_preset: Callable[[], None]
    delete_preset: Callable[[], None]


class GuiView:
    """Builds and renders the Tkinter widgets of the Poliglota window."""

    def __init__(self) -> None:
        """Create an empty view; call :meth:`build` to create the widgets."""
        self.root: tk.Tk | None = None
        self.output_text: tk.Text | None = None
        self.translation_text: tk.Text | None = None
        self.validation_label: ttk.Label | None = None
        self.progress: ttk.Progressbar | None = None
        self.cancel_button: ttk.Button | None = None
        self.preset_combo: ttk.Combobox | None = None
        self.interactive_widgets: list[object] = []
        self.action_buttons: list[object] = []
        self.output_buttons: list[object] = []
        self.field_widgets: dict[str, object] = {}
        self.multiline_fields: dict[str, object] = {}
        self.combo_fields: set[str] = set()
        self.tooltips: list[Tooltip] = []
        self.theme = DEFAULT_THEME
        self._style: ttk.Style | None = None
        self._actions: GuiActions | None = None
        self._translation_variable: object | None = None
        self._drop_target: object | None = None
        self._target_list_frame: ttk.Frame | None = None

    def build(
        self,
        *,
        root: tk.Tk,
        variables: GuiVariables,
        actions: GuiActions,
        version: str,
    ) -> None:
        """Create the whole window content under ``root``."""
        self.root = root
        self._actions = actions
        self._style = self._create_style()
        self.interactive_widgets = []
        self.action_buttons = []
        self.output_buttons = []
        self.field_widgets = {}
        self.multiline_fields = {}
        self.combo_fields = set()
        self.tooltips = []
        self.translation_text = None
        self.preset_combo = None
        self._drop_target = None
        self._target_list_frame = None

        main_frame = ttk.Frame(root, padding=14)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_row = ttk.Frame(main_frame)
        header_row.pack(fill=tk.X)
        ttk.Label(
            header_row,
            text="Poliglota — GUI desktop",
            font=("Segoe UI", 14, "bold"),
        ).pack(side=tk.LEFT)
        theme_combo = ttk.Combobox(
            header_row,
            textvariable=variables.theme,
            values=list(THEME_CHOICES),
            state="readonly",
            width=8,
        )
        theme_combo.pack(side=tk.RIGHT)
        self.interactive_widgets.append(theme_combo)
        self._add_tooltip(theme_combo, "Alterna entre os temas claro e escuro.")
        ttk.Label(header_row, text="Tema:").pack(side=tk.RIGHT, padx=(0, 6))

        self._build_preset_row(main_frame, variables, actions)

        ttk.Label(main_frame, text=f"Versão: {version}", style="Muted.TLabel").pack(anchor="w")
        ttk.Label(
            main_frame,
            text=(
                "A CLI continua sendo a interface oficial; "
                "esta GUI apenas reutiliza a mesma lógica."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(
            main_frame,
            text=(
                "Dica rápida: Ctrl+O para escolher a pasta, Ctrl+L para focar o projeto, "
                "F5 para validar e Esc para cancelar."
            ),
            style="Hint.TLabel",
            wraplength=900,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        self._build_form(main_frame, variables)

        self.validation_label = ttk.Label(main_frame, textvariable=variables.validation)
        self.validation_label.pack(anchor="w", pady=(0, 8))

        self._build_actions(main_frame, actions)

        self.progress = ttk.Progressbar(main_frame, mode="determinate", maximum=100, value=0)
        self.progress.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(main_frame, textvariable=variables.status, style="Muted.TLabel").pack(
            anchor="w",
            pady=(0, 8),
        )

        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(
            output_frame,
            width=120,
            height=18,
            wrap=tk.WORD,
            relief=tk.FLAT,
            highlightthickness=1,
            padx=8,
            pady=6,
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.insert(
            tk.END,
            "Poliglota pronto. Use a CLI ou a GUI para validar, "
            "sincronizar e traduzir recursos locais.\n",
        )

        self._build_output_actions(main_frame, actions)

        with contextlib.suppress(AttributeError, TypeError, tk.TclError):
            self.output_text.configure(state=tk.DISABLED)

        self._focus_first_field()

    def _build_preset_row(
        self,
        parent: ttk.Frame,
        variables: GuiVariables,
        actions: GuiActions,
    ) -> None:
        """Create the preset selector and its save/delete actions."""
        preset_row = ttk.Frame(parent)
        preset_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(preset_row, text="Preset:").pack(side=tk.LEFT, padx=(0, 6))
        self.preset_combo = ttk.Combobox(
            preset_row,
            textvariable=variables.preset,
            values=[NO_PRESET_LABEL],
            state="readonly",
            width=28,
        )
        self.preset_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.interactive_widgets.append(self.preset_combo)
        self._add_tooltip(
            self.preset_combo,
            "Configurações salvas; escolher uma aplica na hora.",
        )
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self.preset_combo.bind(
                "<<ComboboxSelected>>",
                self._event_handler(actions.apply_preset),
            )

        save_button = ttk.Button(preset_row, text="Salvar preset", command=actions.save_preset)
        save_button.pack(side=tk.LEFT, padx=(0, 8))
        self.action_buttons.append(save_button)
        self._add_tooltip(save_button, "Guarda o formulário atual com um nome.")

        delete_button = ttk.Button(preset_row, text="Excluir", command=actions.delete_preset)
        delete_button.pack(side=tk.LEFT)
        self.action_buttons.append(delete_button)
        self._add_tooltip(delete_button, "Remove o preset selecionado.")

    def _add_tooltip(self, widget: object, text: str) -> Tooltip:
        """Attach a hover tooltip to ``widget`` and keep it for cleanup."""
        tooltip = Tooltip(widget, text)
        self.tooltips.append(tooltip)
        return tooltip

    def _build_output_actions(self, parent: ttk.Frame, actions: GuiActions) -> None:
        output_actions = ttk.Frame(parent)
        output_actions.pack(fill=tk.X, pady=(6, 0))
        buttons = (
            ("Copiar", actions.copy_output, "Copia a saída para a área de transferência."),
            ("Salvar", actions.save_output, "Salva a saída exibida em um arquivo .txt."),
            ("Limpar", actions.clear_output, "Limpa a área de saída."),
        )
        for label, command, tip in buttons:
            button = ttk.Button(output_actions, text=label, command=command)
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.output_buttons.append(button)
            self._add_tooltip(button, tip)

    def _build_form(self, parent: ttk.Frame, variables: GuiVariables) -> None:
        form = ttk.Frame(parent)
        form.pack(fill=tk.X, pady=(8, 12))

        ttk.Label(form, text="Projeto:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        project_combo = ttk.Combobox(form, textvariable=variables.project, state="normal")
        self._register_entry(
            "project",
            project_combo,
            row=0,
            column=1,
            sticky="ew",
            tooltip="Pasta raiz do projeto; o histórico de pastas recentes fica na lista.",
            combo=True,
        )
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            project_combo.bind(
                "<<ComboboxSelected>>",
                self._event_handler(self._actions.project_history_selected),
            )
        select_button = ttk.Button(form, text="Selecionar", command=self._actions.choose_project)
        select_button.grid(row=0, column=2, pady=4)
        self.action_buttons.append(select_button)
        self._add_tooltip(select_button, "Escolhe a pasta do projeto (Ctrl+O).")

        ttk.Label(form, text="Formato:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        format_combo = ttk.Combobox(
            form,
            textvariable=variables.format,
            values=list(FORMAT_CHOICES),
            state="readonly",
            width=12,
        )
        format_combo.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)
        self.interactive_widgets.append(format_combo)
        self._add_tooltip(format_combo, "Formato dos arquivos de tradução do projeto.")

        ttk.Label(form, text="Origem:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        source_combo = ttk.Combobox(
            form,
            textvariable=variables.source,
            values=list(LOCALE_CHOICES),
            state="readonly",
            width=14,
        )
        self._register_entry(
            "source",
            source_combo,
            row=2,
            column=1,
            sticky="ew",
            tooltip="Idioma de origem. Escolha um único valor.",
            combo=True,
        )

        ttk.Label(form, text="Destino:").grid(row=2, column=2, sticky="w", padx=(0, 8), pady=4)
        target_selector = ttk.Frame(form)
        target_selector.grid(row=2, column=3, sticky="ew", padx=(0, 8), pady=4)
        self._target_list_frame = ttk.Frame(target_selector)
        self._target_list_frame.pack(fill=tk.X, pady=(0, 4))

        def append_target_locale(selected_locale: str | None = None) -> None:
            locale = (selected_locale or str(target_combo.get())).strip()
            if not locale:
                return
            raw = str(variables.target.get()).strip()
            selected = [part.strip() for part in raw.split(",") if part.strip()]
            if locale not in selected:
                selected.append(locale)
            variables.target.set(",".join(selected))
            _refresh_target_pills()

        def clear_target_locales() -> None:
            variables.target.set("")
            _refresh_target_pills()

        def remove_target_locale(value: str) -> None:
            selected = [
                part.strip() for part in str(variables.target.get()).split(",") if part.strip()
            ]
            filtered = [item for item in selected if item != value]
            variables.target.set(",".join(filtered))
            _refresh_target_pills()

        def _refresh_target_pills() -> None:
            frame = self._target_list_frame
            if frame is None:
                return
            for child in frame.winfo_children():
                with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                    child.destroy()
            selected = [
                part.strip() for part in str(variables.target.get()).split(",") if part.strip()
            ]
            if not selected:
                label = ttk.Label(
                    frame,
                    text="Nenhum destino selecionado",
                    style="Muted.TLabel",
                )
                label.pack(anchor="w")
                return
            for locale in selected:
                pill = ttk.Frame(frame, padding=(8, 4), style="TargetChip.TFrame")
                pill.pack(anchor="w", pady=3, padx=0)
                ttk.Label(pill, text=f"{locale}", style="TLabel").pack(side=tk.LEFT)
                close_button = ttk.Button(
                    pill,
                    text="x",
                    width=2,
                    command=lambda current=locale: remove_target_locale(current),
                )
                close_button.pack(side=tk.LEFT, padx=(6, 0))
                self.interactive_widgets.append(close_button)
                self._add_tooltip(close_button, f"Remover destino {locale}.")

        target_combo = ttk.Combobox(
            target_selector,
            values=list(LOCALE_CHOICES),
            state="readonly",
            width=14,
        )
        target_combo.pack(fill=tk.X, pady=(0, 4))
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            target_combo.bind(
                "<<ComboboxSelected>>",
                self._event_handler(lambda: append_target_locale(str(target_combo.get()))),
            )

        buttons = ttk.Frame(target_selector)
        buttons.pack(fill=tk.X)
        clear_button = ttk.Button(buttons, text="Limpar", command=clear_target_locales)
        clear_button.pack(side=tk.LEFT)

        self.field_widgets["target"] = target_combo
        self.combo_fields.add("target")
        self.interactive_widgets.extend((target_combo, clear_button))
        self._add_tooltip(target_combo, "Selecione um idioma para adicioná-lo aos destinos.")
        self._add_tooltip(clear_button, "Remove todos os idiomas de destino selecionados.")
        _refresh_target_pills()

        ttk.Label(form, text="Texto:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self._build_translation_text(form, variables)

        ttk.Label(form, text="Motor:").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        engine_combo = ttk.Combobox(
            form,
            textvariable=variables.engine,
            values=list(ENGINE_CHOICES),
            state="readonly",
            width=12,
        )
        engine_combo.grid(row=4, column=1, sticky="w", padx=(0, 8), pady=4)
        self.interactive_widgets.append(engine_combo)
        self._add_tooltip(engine_combo, "Motor de tradução usado pela CLI.")

        ttk.Label(form, text="Dispositivo:").grid(row=4, column=2, sticky="w", padx=(0, 8), pady=4)
        device_combo = ttk.Combobox(
            form,
            textvariable=variables.device,
            values=list(DEVICE_CHOICES),
            state="readonly",
            width=12,
        )
        device_combo.grid(row=4, column=3, sticky="w", padx=(0, 8), pady=4)
        self.interactive_widgets.append(device_combo)
        self._add_tooltip(device_combo, "Dispositivo de execução (auto, cpu, cuda, mps, gpu).")

        ttk.Label(form, text="Modelo:").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        model_combo = ttk.Combobox(
            form,
            textvariable=variables.model,
            values=list(MODEL_CHOICES),
            state="normal",
            width=40,
        )
        model_combo.set("Padrão do motor")
        self._register_entry(
            "model",
            model_combo,
            row=5,
            column=1,
            columnspan=3,
            sticky="ew",
            tooltip=(
                "Modelo opcional. Se permanecer em 'Padrão do motor', o sistema "
                "usa o modelo recomendado automaticamente."
            ),
            combo=True,
        )

        sync_toggle = ttk.Checkbutton(
            form,
            text="Executar em modo dry-run",
            variable=variables.dry_run,
        )
        sync_toggle.grid(row=6, column=0, columnspan=4, sticky="w", padx=(0, 8), pady=(4, 0))
        self.interactive_widgets.append(sync_toggle)
        self._add_tooltip(sync_toggle, "Sincroniza sem gravar alterações nos arquivos.")

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

    def _build_translation_text(self, form: ttk.Frame, variables: GuiVariables) -> None:
        """Create the multiline text field and keep it in sync with the variable."""
        text_widget = tk.Text(
            form,
            height=3,
            wrap=tk.WORD,
            relief=tk.FLAT,
            highlightthickness=1,
            padx=6,
            pady=4,
            undo=True,
        )
        text_widget.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4)
        getter = getattr(variables.translation, "get", None)
        if getter is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                initial = str(getter())
                if initial:
                    text_widget.insert("1.0", initial)
        self.translation_text = text_widget
        self.multiline_fields["translation"] = text_widget
        self.field_widgets["translation"] = text_widget
        self.interactive_widgets.append(text_widget)
        self._translation_variable = variables.translation
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            text_widget.bind("<<Modified>>", self._on_translation_modified)
        self._add_tooltip(text_widget, "Texto a traduzir. Enter valida o formulário.")

    def _on_translation_modified(self, _event: object = None) -> None:
        self._sync_translation_text()

    def _sync_translation_text(self) -> None:
        """Copy the multiline widget content into the bound Tk variable."""
        widget = self.translation_text
        variable = self._translation_variable
        if widget is None or variable is None:
            return

        edit_modified = getattr(widget, "edit_modified", None)
        if edit_modified is not None:
            try:
                if not edit_modified():
                    return
            except (AttributeError, RuntimeError, tk.TclError):
                pass

        getter = getattr(widget, "get", None)
        setter = getattr(variable, "set", None)
        if getter is None or setter is None:
            return
        try:
            value = str(getter("1.0", "end-1c"))
            setter(value)
        except (AttributeError, RuntimeError, tk.TclError):
            return
        if edit_modified is not None:
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                edit_modified(arg=False)

    def set_translation_text(self, value: str) -> None:
        """Replace the multiline widget content without echoing the change back."""
        widget = self.translation_text
        if widget is None:
            return

        getter = getattr(widget, "get", None)
        if getter is not None:
            try:
                if str(getter("1.0", "end-1c")) == value:
                    return
            except (AttributeError, RuntimeError, tk.TclError):
                return

        configure = getattr(widget, "configure", None)
        previous_state: str | None = None
        cget = getattr(widget, "cget", None)
        if cget is not None:
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                previous_state = str(cget("state"))
        if configure is not None:
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                configure(state=tk.NORMAL)
        try:
            widget.delete("1.0", tk.END)
            if value:
                widget.insert("1.0", value)
        except (AttributeError, RuntimeError, tk.TclError):
            return
        finally:
            if configure is not None and previous_state is not None:
                with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                    configure(state=previous_state)

    def translation_content(self) -> str:
        """Return the current multiline text content."""
        widget = self.translation_text
        getter = getattr(widget, "get", None) if widget is not None else None
        if getter is None:
            return ""
        try:
            return str(getter("1.0", "end-1c"))
        except (AttributeError, RuntimeError, tk.TclError):
            return ""

    def _register_entry(
        self,
        name: str,
        widget: ttk.Entry,
        *,
        row: int,
        column: int,
        columnspan: int = 1,
        sticky: str = "ew",
        tooltip: str | None = None,
        combo: bool = False,
    ) -> None:
        widget.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky=sticky,
            padx=(0, 8),
            pady=4,
        )
        self.interactive_widgets.append(widget)
        self.field_widgets[name] = widget
        if combo:
            self.combo_fields.add(name)
        if tooltip:
            self._add_tooltip(widget, tooltip)

    def _build_actions(self, parent: ttk.Frame, actions: GuiActions) -> None:
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        self.cancel_button = ttk.Button(
            actions_frame,
            text="Cancelar",
            command=actions.cancel,
            state=tk.DISABLED,
            style="Warning.TButton",
        )
        self.cancel_button.pack(side=tk.RIGHT)
        self._add_tooltip(self.cancel_button, "Interrompe a operação em andamento (Esc).")

        buttons = (
            ("Validar", actions.validate, "Accent.TButton", "Valida os recursos do projeto (F5)."),
            ("Sincronizar", actions.sync, "TButton", "Sincroniza os arquivos de tradução."),
            ("Listar idiomas", actions.list_locales, "TButton", "Lista os locales encontrados."),
            ("Traduzir", actions.translate, "TButton", "Traduz o texto informado no campo Texto."),
            (
                "Traduzir Projeto",
                actions.translate_project,
                "TButton",
                "Traduz todos os recursos do projeto.",
            ),
            (
                "Restaurar padrões",
                actions.restore_defaults,
                "TButton",
                "Volta aos valores padrão, mantendo o tema atual.",
            ),
        )
        for label, command, style, tip in buttons:
            button = ttk.Button(actions_frame, text=label, command=command, style=style)
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.action_buttons.append(button)
            self._add_tooltip(button, tip)

    def _create_style(self) -> ttk.Style | None:
        if self.root is None:
            return None
        try:
            style = ttk.Style(self.root)
            style.theme_use("clam")
        except (AttributeError, RuntimeError, tk.TclError):
            return None
        return style

    def apply_theme(self, name: str) -> str:
        """Apply a theme by name and return the theme that is now active."""
        theme = resolve_theme(name)
        self.theme = theme.name
        self._configure_styles(theme)
        self._configure_output(theme)
        self._configure_text_fields(theme)
        return theme.name

    def _configure_styles(self, theme: Theme) -> None:
        style = self._style
        if style is None:
            return
        with contextlib.suppress(tk.TclError):
            style.configure(
                ".",
                background=theme.background,
                foreground=theme.foreground,
                fieldbackground=theme.surface,
                bordercolor=theme.border,
                focuscolor=theme.accent,
            )
            style.configure("TFrame", background=theme.background)
            style.configure("TLabel", background=theme.background, foreground=theme.foreground)
            style.configure("Muted.TLabel", background=theme.background, foreground=theme.muted)
            style.configure("Hint.TLabel", background=theme.background, foreground=theme.accent)
            style.configure("Ok.TLabel", background=theme.background, foreground=theme.success)
            style.configure("Error.TLabel", background=theme.background, foreground=theme.error)
            style.configure("TButton", padding=(10, 4))
            style.configure("TargetChip.TFrame", background=theme.surface, bordercolor=theme.border)
            style.configure(
                "Accent.TButton",
                background=theme.accent,
                foreground=theme.accent_text,
                bordercolor=theme.accent,
            )
            style.map(
                "Accent.TButton",
                background=[("active", theme.accent)],
                foreground=[("active", theme.accent_text)],
            )
            style.configure(
                "Warning.TButton",
                background=theme.error,
                foreground=theme.accent_text,
                bordercolor=theme.error,
            )
            style.map(
                "Warning.TButton",
                background=[("active", theme.error)],
                foreground=[("active", theme.accent_text)],
            )
            style.configure(
                NORMAL_ENTRY_STYLE,
                fieldbackground=theme.surface,
                foreground=theme.foreground,
                bordercolor=theme.border,
                lightcolor=theme.surface,
                darkcolor=theme.surface,
            )
            style.configure(
                INVALID_ENTRY_STYLE,
                fieldbackground=theme.invalid_background,
                foreground=theme.foreground,
                bordercolor=theme.error,
                lightcolor=theme.error,
                darkcolor=theme.error,
            )
            style.configure(
                "TCombobox",
                fieldbackground=theme.surface,
                background=theme.surface,
                foreground=theme.foreground,
                arrowcolor=theme.foreground,
                bordercolor=theme.border,
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", theme.surface)],
                foreground=[("readonly", theme.foreground)],
            )
            style.configure(
                INVALID_COMBO_STYLE,
                fieldbackground=theme.invalid_background,
                background=theme.invalid_background,
                foreground=theme.foreground,
                arrowcolor=theme.error,
                bordercolor=theme.error,
                lightcolor=theme.error,
                darkcolor=theme.error,
            )
            style.map(
                INVALID_COMBO_STYLE,
                fieldbackground=[("readonly", theme.invalid_background)],
                foreground=[("readonly", theme.foreground)],
            )
            style.configure(
                "TCheckbutton",
                background=theme.background,
                foreground=theme.foreground,
            )
            style.configure(
                "Horizontal.TProgressbar",
                background=theme.accent,
                troughcolor=theme.surface,
                bordercolor=theme.border,
                lightcolor=theme.accent,
                darkcolor=theme.accent,
            )

    def _configure_output(self, theme: Theme) -> None:
        if self.output_text is None:
            return
        with contextlib.suppress(AttributeError, tk.TclError):
            self.output_text.configure(
                background=theme.output_background,
                foreground=theme.output_foreground,
                insertbackground=theme.output_foreground,
                selectbackground=theme.selection,
                selectforeground=theme.output_foreground,
                highlightbackground=theme.border,
                highlightcolor=theme.accent,
            )
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self.output_text.tag_configure(STDERR_TAG, foreground=theme.error)

    def _configure_text_fields(self, theme: Theme) -> None:
        for widget in self.multiline_fields.values():
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                widget.configure(
                    background=theme.surface,
                    foreground=theme.foreground,
                    insertbackground=theme.foreground,
                    selectbackground=theme.selection,
                    selectforeground=theme.foreground,
                    highlightbackground=theme.border,
                    highlightcolor=theme.accent,
                )

    def show_validation_state(self, *, is_error: bool) -> None:
        """Recolor the inline validation label for an error or success state."""
        if self.validation_label is None:
            return
        with contextlib.suppress(AttributeError, tk.TclError):
            self.validation_label.configure(style="Error.TLabel" if is_error else "Ok.TLabel")

    def mark_invalid(self, invalid_fields: Container[str]) -> None:
        """Highlight the fields whose names appear in ``invalid_fields``."""
        for name, widget in self.field_widgets.items():
            is_invalid = name in invalid_fields
            if name in self.multiline_fields:
                self._style_multiline_field(widget, invalid=is_invalid)
                continue
            if name in self.combo_fields:
                style = INVALID_COMBO_STYLE if is_invalid else NORMAL_COMBO_STYLE
            else:
                style = INVALID_ENTRY_STYLE if is_invalid else NORMAL_ENTRY_STYLE
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                widget.configure(style=style)

    def _style_multiline_field(self, widget: object, *, invalid: bool) -> None:
        theme = resolve_theme(self.theme)
        with contextlib.suppress(AttributeError, TypeError, tk.TclError):
            widget.configure(
                highlightcolor=theme.error if invalid else theme.accent,
                highlightbackground=theme.error if invalid else theme.border,
            )

    def focus_field(self, name: str) -> None:
        """Move keyboard focus to the entry registered under ``name``."""
        widget = self.field_widgets.get(name)
        focus_set = getattr(widget, "focus_set", None)
        if focus_set is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            focus_set()

    def set_presets(self, names: list[str], *, selected: str = "") -> None:
        """Fill the preset combobox with ``names`` and select one of them."""
        combo = self.preset_combo
        if combo is None:
            return
        values = [*names, NO_PRESET_LABEL]
        with contextlib.suppress(AttributeError, TypeError, tk.TclError):
            combo.configure(values=values)
        with contextlib.suppress(AttributeError, TypeError, tk.TclError):
            combo.set(selected or NO_PRESET_LABEL)

    def set_recent_projects(self, values: list[str]) -> None:
        """Refresh the project history dropdown without touching the field text."""
        widget = self.field_widgets.get("project")
        configure = getattr(widget, "configure", None)
        if configure is None:
            return
        with contextlib.suppress(AttributeError, TypeError, tk.TclError):
            configure(values=list(values))

    def enable_file_drop(self, callback: Callable[[str], None]) -> bool:
        """Accept dropped folders on the project field, when DnD is available.

        ``tkinterdnd2`` is an optional dependency: without it the window simply
        behaves as before and the caller can tell the user how to enable it.
        """
        target = self.field_widgets.get("project") or self.root
        register = getattr(target, "drop_target_register", None)
        bind = getattr(target, "bind", None)
        if register is None or bind is None:
            return False

        try:
            register(DND_FILES)
        except (AttributeError, RuntimeError, tk.TclError):
            return False

        def on_drop(event: object) -> object:
            paths = parse_drop_paths(str(getattr(event, "data", "") or ""))
            if paths:
                callback(paths[0])
            return getattr(event, "action", None)

        try:
            bind("<<Drop>>", on_drop, add="+")
        except (AttributeError, TypeError, RuntimeError, tk.TclError):
            return False

        self._drop_target = target
        return True

    def set_busy(self, *, busy: bool) -> None:
        """Toggle the progress indicator and the cancel button."""
        if self.progress is not None:
            with contextlib.suppress(AttributeError, tk.TclError):
                if busy:
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(PROGRESS_INTERVAL_MS)
                else:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
        if self.cancel_button is not None:
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                self.cancel_button.configure(state=tk.NORMAL if busy else tk.DISABLED)
                self.cancel_button.configure(style="Warning.TButton" if busy else "TButton")

    @contextlib.contextmanager
    def _writable_output(self) -> Iterator[object]:
        """Temporarily unlock the read-only output pane while writing to it."""
        text = self.output_text
        if text is None:
            yield None
            return
        configure = getattr(text, "configure", None)
        if configure is not None:
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                configure(state=tk.NORMAL)
        try:
            yield text
        finally:
            if configure is not None:
                with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                    configure(state=tk.DISABLED)

    @staticmethod
    def _insert_output_text(widget: object, value: str, *, tags: tuple[str, ...] = ()) -> None:
        """Insert text into a Tk text widget, tolerating minimal test doubles."""
        insert = getattr(widget, "insert", None)
        if insert is None:
            msg = "Text widget does not support insert()"
            raise AttributeError(msg)
        if not tags:
            insert(tk.END, value)
            return
        try:
            insert(tk.END, value, tags)
        except TypeError:
            insert(tk.END, value)

    def show_output(self, text: str) -> bool:
        """Replace the output pane content, returning False when the UI is gone."""
        if self.output_text is None:
            return True
        try:
            with self._writable_output() as widget:
                if widget is None:
                    return True
                widget.delete("1.0", tk.END)
                self._insert_output_text(widget, text.strip() or "Nenhuma saída do comando.")
                widget.see(tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

    def append_output(self, line: str, *, is_error: bool = False) -> bool:
        """Append one streamed line, painting stderr lines with the error color."""
        if self.output_text is None:
            return True
        try:
            with self._writable_output() as widget:
                if widget is None:
                    return True
                tags = (STDERR_TAG,) if is_error else ()
                self._insert_output_text(widget, f"{line}\n", tags=tags)
                widget.see(tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

    def clear_output(self) -> bool:
        """Empty the output pane, returning False when the UI is gone."""
        if self.output_text is None:
            return True
        try:
            with self._writable_output() as widget:
                if widget is None:
                    return True
                widget.delete("1.0", tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

    def output_content(self) -> str:
        """Return the current output pane text, without the trailing newline."""
        text = self.output_text
        getter = getattr(text, "get", None) if text is not None else None
        if getter is None:
            return ""
        try:
            return str(getter("1.0", tk.END)).rstrip("\n")
        except (AttributeError, RuntimeError, tk.TclError):
            return ""

    def geometry(self) -> str:
        """Return the current window geometry, or an empty string when unknown."""
        if self.root is None:
            return ""
        geometry = getattr(self.root, "geometry", None)
        if geometry is None:
            return ""
        try:
            return str(geometry())
        except (AttributeError, RuntimeError, tk.TclError):
            return ""

    def apply_geometry(self, geometry: str) -> str:
        """Restore a saved geometry, clamped to the visible desktop."""
        if self.root is None:
            return DEFAULT_GEOMETRY

        screen_width = 1920
        screen_height = 1080
        with contextlib.suppress(AttributeError, TypeError, ValueError, tk.TclError):
            screen_width = int(self.root.winfo_screenwidth())
            screen_height = int(self.root.winfo_screenheight())

        normalized = normalize_geometry(
            geometry,
            screen_width=screen_width,
            screen_height=screen_height,
        )
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            self.root.geometry(normalized)
        return normalized

    def bind_shortcuts(self) -> None:
        """Bind keyboard flows so the window is accessible without the mouse."""
        actions = self._actions
        if actions is None or self.root is None:
            return

        bindings = {
            "<Control-o>": actions.choose_project,
            "<Control-l>": self._focus_project_field,
            "<F5>": actions.validate,
            "<Escape>": actions.cancel,
        }
        for sequence, callback in bindings.items():
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                self.root.bind(sequence, self._event_handler(callback))

        for name, widget in self.field_widgets.items():
            bind = getattr(widget, "bind", None)
            if bind is None:
                continue
            if name in self.multiline_fields:
                # Enter must insert a newline here; Ctrl+Enter validates instead.
                with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                    bind("<Control-Return>", self._event_handler(actions.validate))
                continue
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                bind("<Return>", self._event_handler(actions.validate))

    def _focus_first_field(self) -> None:
        """Give keyboard focus to the project field on first render."""
        if self.root is None:
            return
        self.focus_field("project")

    def _focus_project_field(self) -> None:
        """Return keyboard focus to the project field for quick navigation."""
        self.focus_field("project")

    @staticmethod
    def _event_handler(callback: Callable[[], None]) -> Callable[[tk.Event], str]:
        def handler(_event: tk.Event) -> str:
            callback()
            return "break"

        return handler
