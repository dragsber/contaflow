import json
from decimal import Decimal


def link_movements(db, outgoing_id, incoming_id, kind="trasferimento"):
    if kind not in ("trasferimento", "prelievo", "giroconto", "rimborso", "storno"):
        raise ValueError("Tipo collegamento non valido")
    if outgoing_id == incoming_id:
        raise ValueError("Seleziona due movimenti distinti")
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        outgoing = db.execute("SELECT * FROM transactions WHERE id=?", (outgoing_id,)).fetchone()
        incoming = db.execute("SELECT * FROM transactions WHERE id=?", (incoming_id,)).fetchone()
        if outgoing is None or incoming is None:
            raise ValueError("Movimento non trovato")
        if outgoing["status"] != "COMPLETATO" or incoming["status"] != "COMPLETATO":
            raise ValueError("Sono collegabili solo movimenti completati")
        debit, credit = Decimal(str(outgoing["amount"])), Decimal(str(incoming["amount"]))
        if debit >= 0 or credit <= 0:
            raise ValueError("Indica prima il movimento in uscita, poi quello in entrata")
        for identifier in (outgoing_id, incoming_id):
            if db.execute(
                "SELECT 1 FROM transfers WHERE movement_out_id=? OR movement_in_id=?",
                (identifier, identifier),
            ).fetchone():
                raise ValueError("Movimento già collegato a un trasferimento")
        if kind in ("rimborso", "storno"):
            if outgoing["currency"] != incoming["currency"]:
                raise ValueError("Rimborso in valuta diversa richiede una valutazione manuale")
            total = sum((Decimal(str(r[0])) for r in db.execute(
                "SELECT amount FROM refunds WHERE original_movement_id=?", (outgoing_id,)
            )), Decimal(0))
            if total + credit > -debit:
                raise ValueError("Rimborso superiore alla spesa originale residua")
            db.execute(
                "INSERT INTO refunds(refund_movement_id,original_movement_id,amount) VALUES(?,?,?)",
                (incoming_id, outgoing_id, str(credit)),
            )
            targets = [(incoming, kind, incoming["classification_status"])]
        else:
            if outgoing["account_id"] == incoming["account_id"]:
                raise ValueError("Un trasferimento richiede conti distinti")
            if outgoing["currency"] == incoming["currency"] and -debit != credit:
                raise ValueError("Gli importi delle due gambe non coincidono, commissioni escluse")
            if kind == "prelievo":
                provider = db.execute("SELECT provider FROM accounts WHERE id=?", (incoming["account_id"],)).fetchone()[0]
                if provider != "CASH":
                    raise ValueError("Il prelievo deve avere come destinazione la cassa")
            for identifier in (outgoing_id, incoming_id):
                if db.execute(
                    "SELECT 1 FROM refunds WHERE original_movement_id=? OR refund_movement_id=?",
                    (identifier, identifier),
                ).fetchone():
                    raise ValueError("Movimento già utilizzato in un rimborso")
            db.execute("INSERT INTO transfers(movement_out_id,movement_in_id) VALUES(?,?)",
                       (outgoing_id, incoming_id))
            targets = [(outgoing, kind, "trasferimento"), (incoming, kind, "trasferimento")]
        for row, nature, state in targets:
            for field, value in (("accounting_nature", nature), ("classification_status", state)):
                if row[field] != value:
                    db.execute(f"UPDATE transactions SET {field}=? WHERE id=?", (value, row["id"]))
                    db.execute(
                        "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                        (row["id"], field, json.dumps(row[field]), json.dumps(value)),
                    )
            db.execute(
                "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                (row["id"], "collegamento_contabile", json.dumps(dict(row)),
                 json.dumps({"uscita": outgoing_id, "entrata": incoming_id, "tipo": kind})),
            )
        if kind in ("rimborso", "storno") and incoming["category_id"] is None and outgoing["category_id"] is not None:
            db.execute("UPDATE transactions SET category_id=? WHERE id=?",
                       (outgoing["category_id"], incoming_id))
            db.execute(
                "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'category_id','null',?)",
                (incoming_id, json.dumps(outgoing["category_id"])),
            )
    return kind


def account_summary(store, account=None):
    rows = store.db.execute("SELECT id,name,currency FROM accounts ORDER BY id").fetchall()
    result = []
    for account_row in rows:
        if account and account_row["name"] != account:
            continue
        balance = income = expenses = fees = Decimal(0)
        for row in store.db.execute(
            "SELECT amount,fee,classification_status,accounting_nature FROM transactions "
            "WHERE account_id=? AND status='COMPLETATO'", (account_row["id"],)
        ):
            amount, fee = Decimal(str(row["amount"])), Decimal(str(row["fee"]))
            balance += amount - fee
            fees += fee
            if row["classification_status"] in ("trasferimento", "escluso") or row["accounting_nature"] in (
                "trasferimento", "prelievo", "giroconto", "escluso",
            ):
                continue
            if row["accounting_nature"] in ("rimborso", "storno") and amount > 0:
                expenses -= amount
            elif amount > 0:
                income += amount
            else:
                expenses -= amount
        result.append({**dict(account_row), "balance": balance, "income": income,
                       "expenses": expenses, "fees": fees})
    return result


def unlink_movement(db, movement_id):
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        targets = set()
        for table, first, second in (
            ("transfers", "movement_out_id", "movement_in_id"),
            ("refunds", "refund_movement_id", "original_movement_id"),
        ):
            links = db.execute(
                f"SELECT * FROM {table} WHERE {first}=? OR {second}=?", (movement_id, movement_id)
            ).fetchall()
            for link in links:
                targets.update((link[first], link[second]) if table == "transfers" else (link[first],))
                db.execute(f"DELETE FROM {table} WHERE id=?", (link["id"],))
        for identifier in targets:
            history = db.execute(
                "SELECT old_value FROM audit WHERE transaction_id=? AND field='collegamento_contabile' "
                "ORDER BY id DESC LIMIT 1", (identifier,),
            ).fetchone()
            previous = json.loads(history[0]) if history and history[0] else {}
            current = db.execute("SELECT * FROM transactions WHERE id=?", (identifier,)).fetchone()
            state, nature = previous.get("classification_status", "in_attesa"), previous.get("accounting_nature", "ordinario")
            db.execute("UPDATE transactions SET classification_status=?,accounting_nature=? WHERE id=?",
                       (state, nature, identifier))
            db.execute(
                "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                (identifier, "scollegamento_contabile", json.dumps(dict(current)),
                 json.dumps({"classification_status": state, "accounting_nature": nature})),
            )
    return len(targets)
