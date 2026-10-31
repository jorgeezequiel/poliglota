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
    THEME_CHOICES,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Container

DEFAULT_GEOMETRY = "960x640"
MIN_WINDOW_WIDTH = 760
MIN_WINDOW_HEIGHT = 500
DEFAULT_WINDOW_OFFSET = 40
MIN_VISIBLE_MARGIN = 120
PROGRESS_INTERVAL_MS = 12

GEOMETRY_PATTERN = re.compile(r"(\d{2,5})x(\d{2,5})(?:([+-]\d{1,5})([+-]\d{1,5}))?")

INVALID_ENTRY_STYLE = "Invalid.TEntry"
NORMAL_ENTRY_STYLE = "TEntry"


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


@dataclass(frozen=True, slots=True)
class GuiActions:
    """Callbacks the window triggers; the app owns their implementation."""

    validate: Callable[[], None]
    sync: Callable[[], None]
    list_locales: Callable[[], None]
    translate: Callable[[], None]
    translate_project: Callable[[], None]
    choose_project: Callable[[], None]
    cancel: Callable[[], None]


class GuiView:
    """Builds and renders the Tkinter widgets of the Poliglota window."""

    def __init__(self) -> None:
        """Create an empty view; call :meth:`build` to create the widgets."""
        self.root: tk.Tk | None = None
        self.output_text: tk.Text | None = None
        self.validation_label: ttk.Label | None = None
        self.progress: ttk.Progressbar | None = None
        self.cancel_button: ttk.Button | None = None
        self.interactive_widgets: list[object] = []
        self.action_buttons: list[object] = []
        self.field_widgets: dict[str, object] = {}
        self.theme = DEFAULT_THEME
        self._style: ttk.Style | None = None
        self._actions: GuiActions | None = None

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
        self.field_widgets = {}

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
        ttk.Label(header_row, text="Tema:").pack(side=tk.RIGHT, padx=(0, 6))

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

    def _build_form(self, parent: ttk.Frame, variables: GuiVariables) -> None:
        form = ttk.Frame(parent)
        form.pack(fill=tk.X, pady=(8, 12))

        ttk.Label(form, text="Projeto:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self._register_entry(
            "project",
            ttk.Entry(form, textvariable=variables.project),
            row=0,
            column=1,
            sticky="ew",
        )
        select_button = ttk.Button(form, text="Selecionar", command=self._actions.choose_project)
        select_button.grid(row=0, column=2, pady=4)
        self.action_buttons.append(select_button)

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

        ttk.Label(form, text="Origem:").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self._register_entry(
            "source",
            ttk.Entry(form, textvariable=variables.source),
            row=2,
            column=1,
            sticky="ew",
        )

        ttk.Label(form, text="Destino:").grid(row=2, column=2, sticky="w", padx=(0, 8), pady=4)
        self._register_entry(
            "target",
            ttk.Entry(form, textvariable=variables.target),
            row=2,
            column=3,
            sticky="ew",
        )

        ttk.Label(form, text="Texto:").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        text_entry = ttk.Entry(form, textvariable=variables.translation)
        text_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4)
        self.interactive_widgets.append(text_entry)

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

        ttk.Label(form, text="Modelo:").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self._register_entry(
            "model",
            ttk.Entry(form, textvariable=variables.model),
            row=5,
            column=1,
            columnspan=3,
            sticky="ew",
        )

        sync_toggle = ttk.Checkbutton(
            form,
            text="Executar em modo dry-run",
            variable=variables.dry_run,
        )
        sync_toggle.grid(row=6, column=0, columnspan=4, sticky="w", padx=(0, 8), pady=(4, 0))
        self.interactive_widgets.append(sync_toggle)

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

    def _register_entry(
        self,
        name: str,
        widget: ttk.Entry,
        *,
        row: int,
        column: int,
        columnspan: int = 1,
        sticky: str = "ew",
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

    def _build_actions(self, parent: ttk.Frame, actions: GuiActions) -> None:
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        self.cancel_button = ttk.Button(
            actions_frame,
            text="Cancelar",
            command=actions.cancel,
            state=tk.DISABLED,
        )
        self.cancel_button.pack(side=tk.RIGHT)

        buttons = (
            ("Validar", actions.validate, "Accent.TButton"),
            ("Sincronizar", actions.sync, "TButton"),
            ("Listar idiomas", actions.list_locales, "TButton"),
            ("Traduzir", actions.translate, "TButton"),
            ("Traduzir Projeto", actions.translate_project, "TButton"),
        )
        for label, command, style in buttons:
            button = ttk.Button(actions_frame, text=label, command=command, style=style)
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.action_buttons.append(button)

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
            style.configure("Ok.TLabel", background=theme.background, foreground=theme.success)
            style.configure("Error.TLabel", background=theme.background, foreground=theme.error)
            style.configure("TButton", padding=(10, 4))
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

    def show_validation_state(self, *, is_error: bool) -> None:
        """Recolor the inline validation label for an error or success state."""
        if self.validation_label is None:
            return
        with contextlib.suppress(AttributeError, tk.TclError):
            self.validation_label.configure(style="Error.TLabel" if is_error else "Ok.TLabel")

    def mark_invalid(self, invalid_fields: Container[str]) -> None:
        """Highlight the entries whose names appear in ``invalid_fields``."""
        for name, widget in self.field_widgets.items():
            style = INVALID_ENTRY_STYLE if name in invalid_fields else NORMAL_ENTRY_STYLE
            with contextlib.suppress(AttributeError, TypeError, tk.TclError):
                widget.configure(style=style)

    def focus_field(self, name: str) -> None:
        """Move keyboard focus to the entry registered under ``name``."""
        widget = self.field_widgets.get(name)
        focus_set = getattr(widget, "focus_set", None)
        if focus_set is None:
            return
        with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
            focus_set()

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

    def show_output(self, text: str) -> bool:
        """Replace the output pane content, returning False when the UI is gone."""
        if self.output_text is None:
            return True
        try:
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, text.strip() or "Nenhuma saída do comando.")
            self.output_text.see(tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

    def append_output(self, line: str) -> bool:
        """Append one streamed line to the output pane, returning False on failure."""
        if self.output_text is None:
            return True
        try:
            self.output_text.insert(tk.END, f"{line}\n")
            self.output_text.see(tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

    def clear_output(self) -> bool:
        """Empty the output pane, returning False when the UI is gone."""
        if self.output_text is None:
            return True
        try:
            self.output_text.delete("1.0", tk.END)
        except (AttributeError, RuntimeError, tk.TclError):
            return False
        return True

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
        """Bind Enter, Ctrl+O, F5 and Escape to their actions."""
        actions = self._actions
        if actions is None or self.root is None:
            return

        bindings = {
            "<Control-o>": actions.choose_project,
            "<F5>": actions.validate,
            "<Escape>": actions.cancel,
        }
        for sequence, callback in bindings.items():
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                self.root.bind(sequence, self._event_handler(callback))

        for widget in self.field_widgets.values():
            bind = getattr(widget, "bind", None)
            if bind is None:
                continue
            with contextlib.suppress(AttributeError, RuntimeError, tk.TclError):
                bind("<Return>", self._event_handler(actions.validate))

    @staticmethod
    def _event_handler(callback: Callable[[], None]) -> Callable[[tk.Event], str]:
        def handler(_event: tk.Event) -> str:
            callback()
            return "break"

        return handler
