"""Tk event-level regression tests for protecting unsaved review edits."""

from __future__ import annotations

import json
import platform
import tkinter as tk
from contextlib import suppress
from time import monotonic
from tkinter import ttk
from typing import TYPE_CHECKING, Any

import pytest

from poliglota.review_window import open_review_window

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module")
def tk_root() -> Any:
    root: tk.Tk | None = None
    try:
        # Tkinter uses one Tcl interpreter per application.  Do not use
        # wait_visibility here: it waits for a *change* in visibility, so it
        # can wait forever if the window is already visible or Aqua does not
        # deliver the expected transition.
        root = tk.Tk()
        print(
            "Tk root initialized: "
            f"system={platform.platform()} python={platform.python_version()} "
            f"tcl={root.tk.call('info', 'patchlevel')} "
            f"windowing_system={root.tk.call('tk', 'windowingsystem')} "
            f"state={root.state()} mapped={root.winfo_ismapped()} "
            f"viewable={root.winfo_viewable()}"
        )
        root.deiconify()
        _wait_until_viewable(root, root)
        print(
            "Tk root mapped: "
            f"state={root.state()} mapped={root.winfo_ismapped()} "
            f"viewable={root.winfo_viewable()}"
        )
    except tk.TclError as exc:
        if root is not None:
            with suppress(tk.TclError):
                root.destroy()
        error = str(exc).lower()
        if "no display name" in error or "couldn't connect to display" in error:
            pytest.skip(f"Tk display is unavailable: {exc}")
        raise
    except BaseException:
        if root is not None:
            with suppress(tk.TclError):
                root.destroy()
        raise
    assert root is not None
    yield root
    with suppress(tk.TclError):
        root.destroy()


def _wait_until_viewable(root: tk.Tk, widget: tk.Misc, timeout_ms: int = 5000) -> None:
    """Pump Tk's normal main loop until mapped, with a bounded diagnostic exit."""
    if widget.winfo_exists() and widget.winfo_viewable():
        return

    deadline = monotonic() + timeout_ms / 1000
    viewable = False

    def inspect_mapping() -> None:
        nonlocal viewable
        if widget.winfo_exists() and widget.winfo_viewable():
            viewable = True
            root.quit()
        elif monotonic() >= deadline:
            root.quit()
        else:
            root.after(25, inspect_mapping)

    root.after(0, inspect_mapping)
    root.mainloop()
    if not viewable:
        details = {
            "system": platform.platform(),
            "python": platform.python_version(),
            "tcl": root.tk.call("info", "patchlevel"),
            "windowing_system": root.tk.call("tk", "windowingsystem"),
            "root_state": root.state(),
            "root_mapped": root.winfo_ismapped(),
            "widget": str(widget),
            "widget_mapped": widget.winfo_ismapped(),
            "widget_viewable": widget.winfo_viewable(),
            "timeout_ms": timeout_ms,
        }
        print(f"Tk mapping diagnostic: {details}")
        message = "Tk widget did not become viewable"
        raise AssertionError(message)


@pytest.fixture
def review_ui(tmp_path: Path, tk_root: tk.Tk) -> Any:
    root = tk_root
    project = tmp_path / "review project"
    project.mkdir()
    (project / "app_home_en_US.arb").write_text(
        json.dumps({"@@locale": "en_US", "first": "First", "second": "Second"}),
        encoding="utf-8",
    )
    generated = project / ".poliglota_translated" / "app_home_es_ES.arb"
    generated.parent.mkdir()
    generated.write_text(
        json.dumps({"@@locale": "es_ES", "first": "Primero", "second": "Segundo"}),
        encoding="utf-8",
    )
    open_review_window(root, project, "arb", "en_US", "es_ES")
    window = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
    tree = next(widget for widget in _walk(window) if isinstance(widget, ttk.Treeview))
    editor = next(
        widget
        for widget in _walk(window)
        if isinstance(widget, tk.Text) and widget.cget("state") != tk.DISABLED
    )
    buttons = {
        widget.cget("text"): widget for widget in _walk(window) if isinstance(widget, ttk.Button)
    }
    # Use a bounded main-loop pass instead of wait_visibility's unbounded
    # wait-for-transition.  Then send the event through Tk's real binding.
    window.deiconify()
    _wait_until_viewable(root, tree)
    assert window.winfo_viewable()
    assert tree.winfo_viewable()
    assert tree.bind("<<TreeviewSelect>>")
    yield root, project, window, tree, editor, buttons
    with suppress(tk.TclError):
        window.destroy()


def _walk(widget: tk.Misc) -> Any:
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _edit(editor: tk.Text, text: str) -> None:
    editor.delete("1.0", "end")
    editor.insert("1.0", text)


def _select(tree: ttk.Treeview, iid: str) -> None:
    tree.selection_set(iid)
    tree.focus(iid)
    # Deliver the actual Tk virtual event synchronously. Pumping the global
    # event loop with root.update() can block on macOS hosted runners.
    tree.event_generate("<<TreeviewSelect>>", when="now")


def test_navigation_can_save_draft_and_preserves_pending_state(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, project, _window, tree, editor, _buttons = review_ui
    _edit(editor, "Edicao temporaria")
    import poliglota.review_window as ui

    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: True)
    _select(tree, "1")
    manifest = json.loads(
        (project / ".poliglota_reviewed" / "review_manifest.json").read_text(encoding="utf-8")
    )
    records = next(iter(manifest["sessions"].values()))
    record = next(record for record in records.values() if record["key"] == "first")
    assert record["value"] == "Edicao temporaria"
    assert record["reviewed"] is False
    assert editor.get("1.0", "end-1c") == "Segundo"


def test_repeated_selection_event_does_not_resolve_the_same_edit_twice(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _project, _window, tree, editor, _buttons = review_ui
    import poliglota.review_window as ui

    prompts: list[str] = []
    monkeypatch.setattr(
        ui.messagebox,
        "askyesnocancel",
        lambda *args, **kwargs: prompts.append("dirty") or True,
    )
    _edit(editor, "Rascunho")
    _select(tree, "1")
    _select(tree, "1")

    assert prompts == ["dirty"]
    assert editor.get("1.0", "end-1c") == "Segundo"


def test_navigation_discard_and_cancel_keep_expected_message(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, project, _window, tree, editor, _buttons = review_ui
    import poliglota.review_window as ui

    _edit(editor, "Não salvar")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: False)
    _select(tree, "1")
    assert editor.get("1.0", "end-1c") == "Segundo"
    assert not (project / ".poliglota_reviewed" / "review_manifest.json").exists()
    _edit(editor, "Manter aqui")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: None)
    _select(tree, "0")
    assert tree.selection() == ("1",)
    assert editor.get("1.0", "end-1c") == "Manter aqui"


def test_failed_save_blocks_navigation_and_export(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, project, _window, tree, editor, _buttons = review_ui
    import poliglota.review_window as ui
    from poliglota.translation_review import TranslationReviewSession

    _edit(editor, "Edição pendente")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        TranslationReviewSession,
        "_write_manifest",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disco indisponível")),
    )
    monkeypatch.setattr(ui.messagebox, "showerror", lambda *args, **kwargs: None)
    _select(tree, "1")
    assert tree.selection() == ("0",)
    assert editor.get("1.0", "end-1c") == "Edição pendente"
    assert not (project / ".poliglota_reviewed" / "review_manifest.json").exists()


def test_cursor_only_is_not_dirty_and_export_dirty_must_be_resolved(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _project, _window, tree, editor, buttons = review_ui
    import poliglota.review_window as ui

    # Cursor/selection movement alone must not prompt.
    editor.mark_set("insert", "1.2")
    prompts: list[str] = []
    ui.messagebox.askyesnocancel = lambda *args, **kwargs: prompts.append("dirty") or None
    _select(tree, "1")
    assert prompts == []
    _edit(editor, "Não exportar sem resolver")
    monkeypatch.setattr(
        ui.filedialog,
        "askdirectory",
        lambda *args, **kwargs: pytest.fail("export proceeded with dirty editor"),
    )
    buttons["Exportar arquivos"].invoke()
    assert prompts == ["dirty"]


def test_close_button_and_window_manager_close_use_dirty_guard(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _project, window, _tree, editor, buttons = review_ui
    import poliglota.review_window as ui

    _edit(editor, "Não perder")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: None)
    buttons["Fechar"].invoke()
    assert window.winfo_exists()
    protocol = root.tk.call("wm", "protocol", window._w, "WM_DELETE_WINDOW")
    root.tk.call(protocol)
    assert window.winfo_exists()
