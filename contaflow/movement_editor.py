import tkinter as tk
from tkinter import ttk, messagebox

from services.editing import NATURES
from services.register import STATUSES


def edit_movements(app):
    ids = [int(iid) for iid in app.table.selection()]
    if not ids:
        messagebox.showwarning("Selezione richiesta", "Seleziona uno o più movimenti.", parent=app)
        return
    row = app.register.rows[str(ids[0])]
    win = tk.Toplevel(app)
    win.title(f"Modifica {len(ids)} movimenti")
    win.transient(app)
    form = ttk.Frame(win, padding=14)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text=f"{len(ids)} movimenti selezionati. Importi bancari non modificabili.",
              wraplength=600).grid(row=0, column=0, columnspan=2, sticky="w")
    keep, clear = "— Mantieni —", "— Nessuno —"
    mappings = {
        "supplier_id": {clear: None, **{f"{r['id']} · {r['name']}": r["id"]
                                      for r in app.store.suppliers()}},
        "category_id": {clear: None, **{f"{r['id']} · {r['name']}": r["id"]
                                      for r in app.store.categories()}},
        "classification_status": {label: key for key, label in STATUSES.items()},
        "accounting_nature": {key.capitalize(): key for key in NATURES},
    }
    labels = ("Fornitore", "Categoria", "Stato", "Natura contabile")
    variables = {}
    for number, ((field, choices), label) in enumerate(zip(mappings.items(), labels), 1):
        initial = keep
        if len(ids) == 1:
            initial = next((label for label, value in choices.items() if value == row[field]), keep)
        var = tk.StringVar(value=initial)
        variables[field] = var
        ttk.Label(form, text=label).grid(row=number, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=var, values=[keep] + list(choices), width=45,
                     state="readonly").grid(row=number, column=1, sticky="ew")
    change_notes = tk.BooleanVar(value=len(ids) == 1)
    ttk.Checkbutton(form, text="Aggiorna note", variable=change_notes).grid(row=5, column=0)
    notes = tk.Text(form, height=4, width=45)
    notes.grid(row=5, column=1)
    if len(ids) == 1:
        notes.insert("1.0", row["notes"])
    scope = tk.StringVar(value="solo")
    ttk.Radiobutton(form, text="Applica solo ai movimenti selezionati", value="solo",
                    variable=scope).grid(row=6, column=0, columnspan=2, sticky="w")
    ttk.Radiobutton(form, text="Crea anche regola per futuri import compatibili", value="futuri",
                    variable=scope).grid(row=7, column=0, columnspan=2, sticky="w")

    def audit():
        if len(ids) != 1:
            messagebox.showinfo("Audit", "Seleziona un solo movimento per consultarne l'audit.", parent=win)
            return
        history = tk.Toplevel(win)
        history.title("Audit movimento")
        text = tk.Text(history, width=100, height=20, wrap="word")
        text.pack(fill="both", expand=True)
        entries = app.store.movement_audit(ids[0])
        text.insert("1.0", "\n".join(
            f"{r['changed_at']} | {r['field']} | {r['old_value']} → {r['new_value']}"
            for r in entries) or "Nessuna modifica registrata.")
        text.configure(state="disabled")

    def save():
        changes = {field: mappings[field][var.get()]
                   for field, var in variables.items() if var.get() != keep}
        if change_notes.get():
            changes["notes"] = notes.get("1.0", "end-1c")
        summary = ", ".join(changes) or "Nessuna variazione dei campi"
        if not messagebox.askyesno(
            "Conferma modifica",
            f"Verranno modificati {len(ids)} movimenti.\nCampi: {summary}\n"
            f"Regola per i futuri import: {'sì' if scope.get() == 'futuri' else 'no'}",
            parent=win,
        ):
            return
        try:
            app.store.update_movements(ids, changes, remember=scope.get() == "futuri")
        except Exception as error:
            messagebox.showerror("Modifiche non salvate", str(error), parent=win)
            return
        win.destroy()
        app.refresh_all()

    ttk.Button(form, text="Consulta audit", command=audit).grid(row=8, column=0, pady=10)
    ttk.Button(form, text="Salva", command=save).grid(row=8, column=1, sticky="e", pady=10)
    win.grab_set()
