import json

from services.register import STATUSES

NATURES = ("ordinario", "trasferimento", "prelievo", "giroconto", "rimborso", "storno", "escluso")


def remember_supplier_alias(store, description, supplier, category, movement_id=None):
    db = store.db
    alias = store.normalize_description(description)
    if not alias:
        raise ValueError("Descrizione non valida per una regola")
    if db.execute("SELECT 1 FROM suppliers WHERE id=? AND archived=0", (supplier,)).fetchone() is None:
        raise ValueError("Scegli un fornitore attivo per la regola futura")
    previous = db.execute("SELECT * FROM supplier_aliases WHERE normalized_alias=?", (alias,)).fetchone()
    if previous and (previous["supplier_id"] != supplier or previous["archived"]):
        raise ValueError("Alias già riservato. Controlla gli alias in Fornitori.")
    db.execute(
        "INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed,category_id) "
        "VALUES(?,?,1,?) ON CONFLICT(normalized_alias) DO UPDATE SET "
        "confirmed=1,category_id=excluded.category_id",
        (alias, supplier, category),
    )
    db.execute(
        "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
        (movement_id, "regola_futura", json.dumps(dict(previous) if previous else None),
         json.dumps({"alias": alias, "supplier_id": supplier, "category_id": category})),
    )


def update_movements(store, movement_ids, changes, remember=False):
    ids = list(dict.fromkeys(int(value) for value in movement_ids))
    if not ids:
        raise ValueError("Seleziona almeno un movimento")
    allowed = {"supplier_id", "category_id", "classification_status", "notes", "accounting_nature"}
    if set(changes) - allowed:
        raise ValueError("Campo non modificabile. Gli importi bancari sono immutabili")
    if "classification_status" in changes and changes["classification_status"] not in STATUSES:
        raise ValueError("Stato non valido")
    if "accounting_nature" in changes and changes["accounting_nature"] not in NATURES:
        raise ValueError("Natura contabile non valida")
    changes = dict(changes)
    db = store.db
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        for field, table in (("supplier_id", "suppliers"), ("category_id", "categories")):
            value = changes.get(field)
            if value is not None and db.execute(
                f"SELECT 1 FROM {table} WHERE id=? AND archived=0", (value,)
            ).fetchone() is None:
                raise ValueError("Fornitore o categoria non disponibile")
        category = db.execute(
            "SELECT category_type FROM categories WHERE id=?", (changes.get("category_id"),)
        ).fetchone()
        if category and category[0] == "trasferimento":
            changes["classification_status"] = "trasferimento"
        if changes.get("classification_status") == "trasferimento" or changes.get("accounting_nature") in (
            "trasferimento", "prelievo", "giroconto",
        ):
            changes["classification_status"] = "trasferimento"
            if changes.get("accounting_nature") not in ("prelievo", "giroconto"):
                changes["accounting_nature"] = "trasferimento"
        if changes.get("classification_status") == "escluso" or changes.get("accounting_nature") == "escluso":
            changes["classification_status"], changes["accounting_nature"] = "escluso", "escluso"
        for movement_id in ids:
            row = db.execute("SELECT * FROM transactions WHERE id=?", (movement_id,)).fetchone()
            if row is None:
                raise ValueError("Movimento non trovato")
            if "category_id" in changes and row["subcategory_id"] is not None and changes["category_id"] != row["category_id"]:
                raise ValueError("La categoria ha una sottovoce associata. Rimuovi prima la sottovoce con conferma.")
            transfer = db.execute(
                "SELECT 1 FROM transfers WHERE movement_out_id=? OR movement_in_id=?", (movement_id, movement_id)
            ).fetchone()
            if transfer and any(field in changes and changes[field] != row[field]
                                for field in ("classification_status", "accounting_nature")):
                raise ValueError("Scollega il trasferimento prima di cambiarne stato o natura")
            updates = {**changes, "classification_origin": "confermata" if remember else "manuale"}
            supplier = changes.get("supplier_id", row["supplier_id"])
            category = changes.get("category_id", row["category_id"])
            if "supplier_id" in changes or remember:
                updates["supplier_origin"] = updates["classification_origin"] if supplier is not None else None
            if remember:
                if supplier is None:
                    raise ValueError("Scegli un fornitore per la regola futura")
                remember_supplier_alias(store, row["description"], supplier, category, movement_id)
            for field, value in updates.items():
                if row[field] != value:
                    db.execute(f"UPDATE transactions SET {field}=? WHERE id=?", (value, movement_id))
                    db.execute(
                        "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                        (movement_id, field, json.dumps(row[field]), json.dumps(value)),
                    )
    return len(ids)


def movement_audit(db, movement_id):
    return db.execute(
        "SELECT field,old_value,new_value,changed_at FROM audit WHERE transaction_id=? ORDER BY id",
        (movement_id,),
    ).fetchall()
