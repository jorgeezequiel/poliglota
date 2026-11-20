"""Tkinter window for manually reviewing generated localization files."""

from __future__ import annotations

import tkinter as tk
from datetime import UTC, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from poliglota.translation_review import ReviewItem, TranslationReviewSession


def open_review_window(
    parent: tk.Misc, root: Path, format_name: str, source: str, target: str
) -> None:
    """Open a persistent review editor for an existing translation run."""
    try:
        session = TranslationReviewSession(root, format_name, source, target)
    except (OSError, ValueError, KeyError) as exc:
        messagebox.showerror("Revisar traduções", str(exc), parent=parent)
        return
    if not session.items:
        messagebox.showinfo(
            "Revisar traduções",
            "Nenhuma tradução preliminar foi encontrada. Traduza o projeto primeiro.",
            parent=parent,
        )
        return

    window = tk.Toplevel(parent)
    window.title(f"Revisar traduções — {source} → {target}")
    window.geometry("980x700")
    window.minsize(760, 520)
    window.transient(parent)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)

    summary = tk.StringVar()
    ttk.Label(window, textvariable=summary).grid(row=0, column=0, sticky="ew", padx=10, pady=8)
    body = ttk.Panedwindow(window, orient=tk.HORIZONTAL)
    body.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
    listing = ttk.Frame(body)
    editor = ttk.Frame(body, padding=(10, 0, 0, 0))
    body.add(listing, weight=1)
    body.add(editor, weight=3)
    listing.rowconfigure(0, weight=1)
    listing.columnconfigure(0, weight=1)
    tree = ttk.Treeview(listing, columns=("state", "key"), show="headings", selectmode="browse")
    tree.heading("state", text="Estado")
    tree.heading("key", text="Chave")
    tree.column("state", width=88, stretch=False)
    tree.column("key", width=220)
    scroll = ttk.Scrollbar(listing, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")
    editor.columnconfigure(0, weight=1)
    editor.rowconfigure(5, weight=1)

    key_label = tk.StringVar(value="Selecione uma mensagem")
    ttk.Label(editor, textvariable=key_label, font=("Segoe UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", pady=(0, 6)
    )
    context_label = tk.StringVar(value="")
    ttk.Label(editor, textvariable=context_label, wraplength=650).grid(
        row=1, column=0, sticky="w", pady=(0, 6)
    )
    ttk.Label(editor, text="Original").grid(row=2, column=0, sticky="w")
    original = tk.Text(editor, height=4, wrap="word", state=tk.DISABLED)
    original.grid(row=3, column=0, sticky="ew", pady=(2, 8))
    ttk.Label(editor, text="Tradução revisável").grid(row=4, column=0, sticky="w")
    translation = tk.Text(editor, height=8, wrap="word", undo=True)
    translation.grid(row=5, column=0, sticky="nsew", pady=(2, 8))

    item_by_id: dict[str, ReviewItem] = {}
    for number, item in enumerate(session.items):
        identifier = str(number)
        item_by_id[identifier] = item
        tree.insert(
            "",
            tk.END,
            iid=identifier,
            values=("Revisada" if item.reviewed else "Pendente", item.key),
        )

    current: ReviewItem | None = None
    current_iid: str | None = None
    loading = False

    def set_text(widget: tk.Text, value: str, *, readonly: bool = False) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        if readonly:
            widget.configure(state=tk.DISABLED)

    def selected_item() -> ReviewItem | None:
        selected = tree.selection()
        return item_by_id.get(selected[0]) if selected else None

    def refresh() -> None:
        summary.set(
            f"{len(session.items) - session.pending_count}/{len(session.items)} revisadas. "
            "Originais preservados."
        )
        if current is None:
            return
        selected = tree.selection()
        if selected:
            item = item_by_id[selected[0]]
            state = next(
                (
                    candidate.reviewed
                    for candidate in session.items
                    if (candidate.file, candidate.key) == (item.file, item.key)
                ),
                False,
            )
            tree.set(selected[0], "state", "Revisada" if state else "Pendente")

    def is_dirty() -> bool:
        return bool(current is not None and translation.get("1.0", "end-1c") != current.value)

    def resolve_dirty() -> bool:
        """Resolve the editor buffer before navigation, close, or export."""
        if not is_dirty():
            return True
        choice = messagebox.askyesnocancel(
            "Alterações não salvas",
            "A tradução foi alterada.\n\n"
            "Sim: salvar rascunho e continuar.\n"
            "Não: descartar as alterações e continuar.\n"
            "Cancelar: permanecer nesta mensagem.",
            parent=window,
        )
        if choice is None:
            return False
        if choice:
            before = current
            save(reviewed=False)
            return before is not None and current is not before and not is_dirty()
        return True

    def select_item(_event: object = None) -> None:
        nonlocal current, current_iid, loading
        if loading:
            return
        selected = tree.selection()
        target_iid = selected[0] if selected else None
        if target_iid is None:
            return
        # Tk may deliver a second selection event after we restore the old row.
        # Never reload the active row from disk in response to that duplicate.
        if target_iid == current_iid:
            return
        if current is not None and target_iid != current_iid and not resolve_dirty():
            loading = True
            tree.selection_remove(tree.selection())
            if current_iid is not None:
                tree.selection_set(current_iid)
                tree.focus(current_iid)
            loading = False
            return
        current_iid = target_iid
        current = item_by_id[target_iid]
        key_label.set(f"{current.key} — {current.file}")
        context = f"Contexto: {current.context}" if current.context else ""
        if current.stale:
            context += (
                "\nRevisão anterior desatualizada: reavalie esta mensagem antes de aprová-la."
            )
        if current.previous_review is not None:
            context += f"\nRevisão anterior: {current.previous_review}"
        context_label.set(context)
        set_text(original, current.source, readonly=True)
        set_text(translation, current.value)

    tree.bind("<<TreeviewSelect>>", select_item)

    def save(*, reviewed: bool) -> None:
        nonlocal current
        item = current
        if item is None:
            return
        value = translation.get("1.0", "end-1c")
        try:
            session.save(item.file, item.key, value, reviewed=reviewed)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=window)
            return
        # Reload the item state while retaining the current editor contents.
        current = next(
            candidate
            for candidate in session.items
            if (candidate.file, candidate.key) == (item.file, item.key)
        )
        set_text(translation, current.value)
        selected = tree.selection()
        if selected:
            tree.set(selected[0], "state", "Revisada" if current.reviewed else "Pendente")
        refresh()

    def export() -> None:
        if not resolve_dirty():
            return
        if session.pending_count and not messagebox.askyesno(
            "Traduções pendentes",
            f"{session.pending_count} mensagens ainda estão pendentes. "
            "A exportação incluirá essas traduções preliminares junto com as revisões. "
            "Deseja continuar?",
            parent=window,
        ):
            return
        destination = filedialog.askdirectory(
            parent=window,
            title="Escolha onde criar uma nova pasta para os arquivos revisados",
            mustexist=False,
        )
        if not destination:
            return
        export_root = Path(destination) / f"poliglota-reviewed-{session.target}"
        if export_root.exists():
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            export_root = export_root.with_name(f"{export_root.name}-{timestamp}")
        try:
            result = session.export(export_root)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Exportação não concluída", str(exc), parent=window)
            return
        messagebox.showinfo("Exportação concluída", str(result), parent=window)

    buttons = ttk.Frame(window)
    buttons.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
    ttk.Button(buttons, text="Salvar rascunho", command=lambda: save(reviewed=False)).pack(
        side=tk.LEFT, padx=(0, 6)
    )
    ttk.Button(buttons, text="Marcar revisada", command=lambda: save(reviewed=True)).pack(
        side=tk.LEFT, padx=6
    )
    ttk.Button(buttons, text="Exportar arquivos", command=export).pack(side=tk.LEFT, padx=6)

    def close() -> None:
        if resolve_dirty():
            window.destroy()

    ttk.Button(buttons, text="Fechar", command=close).pack(side=tk.RIGHT)
    window.protocol("WM_DELETE_WINDOW", close)
    tree.selection_set("0")
    tree.focus("0")
    select_item()
    refresh()
