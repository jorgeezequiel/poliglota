"""Tk event-level regression tests for protecting unsaved review edits."""

from __future__ import annotations

import json
import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import TYPE_CHECKING, Any

import pytest

from poliglota.review_window import open_review_window

if TYPE_CHECKING:
    from pathlib import Path

_ROOT: tk.Tk | None = None


@pytest.fixture
def review_ui(tmp_path: Path) -> Any:
    global _ROOT
    try:
        if _ROOT is None:
            _ROOT = tk.Tk()
            _ROOT.withdraw()
        root = _ROOT
    except tk.TclError as exc:
        pytest.skip(f"Tk display is unavailable: {exc}")
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
    root.update()
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
    yield root, project, window, tree, editor, buttons
    with suppress(tk.TclError):
        window.destroy()
        root.update()


def _walk(widget: tk.Misc) -> Any:
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _edit(editor: tk.Text, text: str) -> None:
    editor.delete("1.0", "end")
    editor.insert("1.0", text)


def _select(tree: ttk.Treeview, iid: str, root: tk.Tk) -> None:
    tree.selection_set(iid)
    tree.focus(iid)
    tree.event_generate("<<TreeviewSelect>>")
    root.update()


def test_navigation_can_save_draft_and_preserves_pending_state(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project, _window, tree, editor, _buttons = review_ui
    _edit(editor, "Edicao temporaria")
    import poliglota.review_window as ui

    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: True)
    _select(tree, "1", root)
    manifest = json.loads(
        (project / ".poliglota_reviewed" / "review_manifest.json").read_text(encoding="utf-8")
    )
    records = next(iter(manifest["sessions"].values()))
    record = next(record for record in records.values() if record["key"] == "first")
    assert record["value"] == "Edicao temporaria"
    assert record["reviewed"] is False
    assert editor.get("1.0", "end-1c") == "Segundo"


def test_navigation_discard_and_cancel_keep_expected_message(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, project, _window, tree, editor, _buttons = review_ui
    import poliglota.review_window as ui

    _edit(editor, "Não salvar")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: False)
    _select(tree, "1", root)
    assert editor.get("1.0", "end-1c") == "Segundo"
    assert not (project / ".poliglota_reviewed" / "review_manifest.json").exists()
    _edit(editor, "Manter aqui")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: None)
    _select(tree, "0", root)
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
    _select(tree, "1", _root)
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
    _select(tree, "1", _root)
    assert prompts == []
    _edit(editor, "Não exportar sem resolver")
    monkeypatch.setattr(
        ui.filedialog,
        "askdirectory",
        lambda *args, **kwargs: pytest.fail("export proceeded with dirty editor"),
    )
    buttons["Exportar arquivos"].invoke()
    _root.update()
    assert prompts == ["dirty"]


def test_close_button_and_window_manager_close_use_dirty_guard(
    review_ui: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _project, window, _tree, editor, buttons = review_ui
    import poliglota.review_window as ui

    _edit(editor, "Não perder")
    monkeypatch.setattr(ui.messagebox, "askyesnocancel", lambda *args, **kwargs: None)
    buttons["Fechar"].invoke()
    root.update()
    assert window.winfo_exists()
    protocol = root.tk.call("wm", "protocol", window._w, "WM_DELETE_WINDOW")
    root.tk.call(protocol)
    root.update()
    assert window.winfo_exists()
