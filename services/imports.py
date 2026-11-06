import json
from dataclasses import dataclass
from pathlib import Path

from adapters.revolut import fingerprint, reconcile
from adapters.statements import RevolutCSVAdapter


@dataclass(frozen=True)
class ImportPreview:
    payload: bytes
    filename: str
    account: str
    total: int
    importable: int
    duplicates: int
    excluded: int
    currency: str
    anomalies: tuple
    pending_operations: int = 0


def preview_import(store, path, account):
    row = store.db.execute(
        "SELECT currency,provider,COALESCE(import_identity,name) AS identity "
        "FROM accounts WHERE name=? AND archived=0", (account,),
    ).fetchone()
    if row is None or row["provider"] != "REVOLUT":
        raise ValueError("Seleziona un conto Revolut configurato")
    payload = Path(path).read_bytes()
    rows = RevolutCSVAdapter().read(payload)
    anomalies = reconcile(rows)
    seen, duplicates, excluded, pending = set(), 0, 0, 0
    for item in rows:
        state = item.get("State", "").strip().upper()
        if state != "COMPLETATO":
            excluded += 1
            if state in ("PENDING", "IN SOSPESO", "IN ATTESA", "NON CONTABILIZZATO"):
                pending += 1
            continue
        if item["Valuta"].strip().upper() != row["currency"].upper():
            raise ValueError("Valuta CSV incompatibile con il conto selezionato")
        identity = fingerprint(row["identity"], item)
        if identity in seen or store.db.execute(
            "SELECT 1 FROM transactions WHERE fingerprint=?", (identity,)
        ).fetchone():
            duplicates += 1
        seen.add(identity)
    return ImportPreview(payload, Path(path).name, account, len(rows),
                         len(rows)-duplicates-excluded, duplicates, excluded, row["currency"], tuple(anomalies), pending)


def confirm_import(store, preview):
    rows = RevolutCSVAdapter().read(preview.payload)
    result = store.import_revolut_detailed(preview.filename, preview.account, rows=rows)
    return {**result, "anomalies": list(preview.anomalies)}


def batch_dependencies(db, batch_id):
    ids = [row[0] for row in db.execute("SELECT id FROM transactions WHERE importation_id=?", (batch_id,))]
    if not ids:
        return {"movements": 0, "manual": 0, "transfers": 0, "refunds": 0}
    placeholders = ",".join("?" for _ in ids)
    manual = db.execute(
        f"SELECT COUNT(DISTINCT transaction_id) FROM audit WHERE transaction_id IN ({placeholders})", ids
    ).fetchone()[0]
    counts = {}
    for table, first, second in (
        ("transfers", "movement_out_id", "movement_in_id"),
        ("refunds", "refund_movement_id", "original_movement_id"),
    ):
        counts[table] = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {first} IN ({placeholders}) OR {second} IN ({placeholders})",
            ids + ids,
        ).fetchone()[0]
    return {"movements": len(ids), "manual": manual, **counts}


def cancel_batch(db, batch_id, confirm_dependencies=False):
    # One write transaction prevents dependencies from changing between check and cancellation.
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso prima di annullare un lotto")
    with db:
        db.execute("BEGIN IMMEDIATE")
        batch = db.execute("SELECT result FROM importations WHERE id=?", (batch_id,)).fetchone()
        if batch is None or batch[0] != "completed":
            raise ValueError("Lotto non disponibile per l'annullamento")
        dependencies = batch_dependencies(db, batch_id)
        if any(dependencies[key] for key in ("manual", "transfers", "refunds")) and not confirm_dependencies:
            raise ValueError("Dipendenze presenti. Serve una conferma specifica")
        rows = db.execute("SELECT * FROM transactions WHERE importation_id=?", (batch_id,)).fetchall()
        ids = {row["id"] for row in rows}
        for table, first, second in (
            ("transfers", "movement_out_id", "movement_in_id"),
            ("refunds", "refund_movement_id", "original_movement_id"),
        ):
            links = db.execute(f"SELECT * FROM {table}").fetchall()
            for link in links:
                if link[first] in ids or link[second] in ids:
                    for counterpart in (link[first], link[second]):
                        if counterpart not in ids:
                            current = db.execute("SELECT * FROM transactions WHERE id=?", (counterpart,)).fetchone()
                            db.execute(
                                "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                                (counterpart, "scollegamento_lotto", json.dumps(dict(current)), str(batch_id)),
                            )
                            if table == "transfers":
                                history = db.execute(
                                    "SELECT old_value FROM audit WHERE transaction_id=? "
                                    "AND field='collegamento_contabile' ORDER BY id DESC LIMIT 1",
                                    (counterpart,),
                                ).fetchone()
                                previous = json.loads(history[0]) if history and history[0] else {}
                                db.execute(
                                    "UPDATE transactions SET accounting_nature=?,classification_status=? WHERE id=?",
                                    (previous.get("accounting_nature", "ordinario"),
                                     previous.get("classification_status", "in_attesa"), counterpart),
                                )
                    db.execute(
                        "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(NULL,?,?,NULL)",
                        (f"annullamento_{table}", json.dumps(dict(link))),
                    )
                    db.execute(f"DELETE FROM {table} WHERE id=?", (link["id"],))
        for row in rows:
            db.execute(
                "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,NULL)",
                (row["id"], "annullamento_lotto", json.dumps(dict(row), ensure_ascii=False)),
            )
            db.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
        db.execute("UPDATE importations SET result='cancelled' WHERE id=?", (batch_id,))
    return dependencies
