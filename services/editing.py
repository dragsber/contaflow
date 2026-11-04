import json

from services.register import STATUSES

NATURES = ("ordinario", "trasferimento", "prelievo", "giroconto", "rimborso", "storno", "escluso")


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
            transfer = db.execute(
                "SELECT 1 FROM transfers WHERE movement_out_id=? OR movement_in_id=?", (movement_id, movement_id)
            ).fetchone()
            if transfer and any(field in changes and changes[field] != row[field]
                                for field in ("classification_status", "accounting_nature")):
                raise ValueError("Scollega il trasferimento prima di cambiarne stato o natura")
            updates = {**changes, "classification_origin": "confermata" if remember else "manuale"}
            supplier = changes.get("supplier_id", row["supplier_id"])
            category = changes.get("category_id", row["category_id"])
            if remember:
                if supplier is None:
                    raise ValueError("Scegli un fornitore per la regola futura")
                alias = store.normalize_description(row["description"])
                if not alias:
                    raise ValueError("Descrizione non valida per una regola")
                previous = db.execute(
                    "SELECT * FROM supplier_aliases WHERE normalized_alias=?", (alias,)
                ).fetchone()
                db.execute(
                    "INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) "
                    "VALUES(?,?,1) ON CONFLICT(normalized_alias) DO UPDATE SET "
                    "supplier_id=excluded.supplier_id,confirmed=1", (alias, supplier),
                )
                old_category = db.execute(
                    "SELECT habitual_category_id FROM suppliers WHERE id=?", (supplier,)
                ).fetchone()[0]
                db.execute("UPDATE suppliers SET habitual_category_id=? WHERE id=?", (category, supplier))
                db.execute(
                    "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                    (movement_id, "regola_futura", json.dumps(dict(previous) if previous else None),
                     json.dumps({"alias": alias, "supplier_id": supplier, "category_id": category,
                                 "previous_category_id": old_category})),
                )
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
