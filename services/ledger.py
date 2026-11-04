import json
from decimal import Decimal


def accounts(db, search="", include_archived=False):
    return db.execute(
        "SELECT l.*,(SELECT group_concat(c.name,' | ') FROM ledger_categories r "
        "JOIN categories c ON c.id=r.category_id WHERE r.ledger_id=l.id) AS category_labels "
        "FROM ledger_accounts l WHERE (l.archived=0 OR ?) AND "
        "(instr(lower(l.code),lower(?))>0 OR instr(lower(l.description),lower(?))>0) ORDER BY l.code",
        (include_archived, search, search),
    ).fetchall()


def preview(db, records):
    seen, changes = {}, []
    for row in records:
        code, description = row["code"], row["description"]
        if not isinstance(code,str) or not isinstance(description,str) or not code.strip() or not description.strip():
            raise ValueError("Codice e descrizione devono essere testi espliciti non vuoti")
        if code in seen and seen[code] != description:
            raise ValueError("Descrizioni discordanti per il codice " + code)
        seen[code] = description
        old = db.execute("SELECT description FROM ledger_accounts WHERE code=?", (code,)).fetchone()
        if old is None:
            changes.append(f"Nuovo conto {code} — {description}")
        elif old[0] != description:
            changes.append(f"Modifica {code}: {old[0]} → {description}")
        if row.get("category"):
            changes.append(f"Relazione esplicita {code} / categoria {row['category']}")
        if row.get("supplier"):
            changes.append(f"Associazione {code} / fornitore {row['supplier']} (nessuna modifica anagrafica)")
    return changes


def import_chart(db, records, source_name, expected=None):
    with db:
        db.execute("BEGIN IMMEDIATE")
        if expected is not None and import_signature(db) != expected:
            raise ValueError("Le anagrafiche sono cambiate. Riapri l'anteprima prima di confermare.")
        preview(db, records)
        for row in records:
            old = db.execute("SELECT * FROM ledger_accounts WHERE code=?", (row["code"],)).fetchone()
            if old is None:
                ledger_id = db.execute(
                    "INSERT INTO ledger_accounts(code,description,origin) VALUES(?,?,'importato')",
                    (row["code"], row["description"]),
                ).lastrowid
            else:
                ledger_id = old["id"]
                if old["description"] != row["description"]:
                    db.execute("UPDATE ledger_accounts SET description=? WHERE id=?", (row["description"], ledger_id))
                    db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                               (f"conto_contabile:{row['code']}", old["description"], row["description"]))
            if row.get("category"):
                category = db.execute("SELECT id FROM categories WHERE name=?", (row["category"],)).fetchone()
                if category is None:
                    raise ValueError("Categoria non presente: " + row["category"] + ". Creala o correggi la mappatura.")
                db.execute("INSERT OR IGNORE INTO ledger_categories VALUES(?,?)", (ledger_id, category[0]))
            if row.get("supplier"):
                supplier = db.execute("SELECT id FROM suppliers WHERE name=?", (row["supplier"],)).fetchone()
                if supplier is None:
                    supplier_id = db.execute("INSERT INTO suppliers(name) VALUES(?)", (row["supplier"],)).lastrowid
                else:
                    supplier_id = supplier[0]
                db.execute("INSERT OR IGNORE INTO supplier_ledger(supplier_id,ledger_id) VALUES(?,?)",
                           (supplier_id, ledger_id))
        db.execute("INSERT INTO ledger_imports(source_name) VALUES(?)", (source_name,))


def edit_account(db, ledger_id, description, archived):
    if not description:
        raise ValueError("Descrizione obbligatoria")
    with db:
        old = db.execute("SELECT * FROM ledger_accounts WHERE id=?", (ledger_id,)).fetchone()
        if old is None:
            raise ValueError("Conto contabile non trovato")
        db.execute("UPDATE ledger_accounts SET description=?,archived=? WHERE id=?",
                   (description, int(archived), ledger_id))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"conto_contabile:{old['code']}", json.dumps(dict(old)), json.dumps([description, archived])))


def manual_account(db, code, description, *, explicit_request=False):
    if not explicit_request or not db.execute("SELECT 1 FROM ledger_imports LIMIT 1").fetchone():
        raise ValueError("Creazione manuale consentita solo su richiesta esplicita dopo l'importazione")
    if not code or not description:
        raise ValueError("Codice e descrizione obbligatori")
    with db:
        return db.execute("INSERT INTO ledger_accounts(code,description,origin) VALUES(?,?,'manuale')",
                          (code, description)).lastrowid


def associate(db, supplier_id, ledger_ids, habitual=None, alias_id=None):
    ids = set(ledger_ids)
    if habitual is not None and habitual not in ids:
        raise ValueError("Il conto abituale deve appartenere ai conti associati")
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM suppliers WHERE id=?", (supplier_id,)).fetchone():
            raise ValueError("Fornitore non trovato")
        for identifier in ids:
            if not db.execute("SELECT 1 FROM ledger_accounts WHERE id=? AND archived=0",(identifier,)).fetchone():
                raise ValueError("Conto contabile non disponibile")
        if alias_id is not None:
            alias = db.execute("SELECT supplier_id FROM supplier_aliases WHERE id=?", (alias_id,)).fetchone()
            if alias is None or alias[0] != supplier_id:
                raise ValueError("Alias non appartenente al fornitore")
            previous = [tuple(r) for r in db.execute("SELECT * FROM alias_ledger WHERE alias_id=?", (alias_id,))]
            db.execute("DELETE FROM alias_ledger WHERE alias_id=?", (alias_id,))
            for identifier in ids:
                db.execute("INSERT INTO alias_ledger VALUES(?,?)", (alias_id, identifier))
        else:
            previous = [tuple(r) for r in db.execute("SELECT * FROM supplier_ledger WHERE supplier_id=?", (supplier_id,))]
            db.execute("DELETE FROM supplier_ledger WHERE supplier_id=?", (supplier_id,))
            for identifier in ids:
                db.execute("INSERT INTO supplier_ledger VALUES(?,?,?)",
                           (supplier_id, identifier, int(identifier == habitual)))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"associazione_contabile:{supplier_id}:{alias_id}", json.dumps(previous),
                    json.dumps({"conti":sorted(ids),"abituale":habitual})))


def candidates(store, description, supplier_id):
    db = store.db
    key = store.normalize_description(description)
    # Explicitly remembered account choices are confirmed assignments.
    confirmed = db.execute(
        "SELECT r.ledger_id FROM ledger_rules r JOIN ledger_accounts l ON l.id=r.ledger_id "
        "WHERE r.description=? AND l.archived=0", (key,),
    ).fetchone()
    if confirmed:
        return [confirmed[0]]
    alias = db.execute("SELECT id,confirmed FROM supplier_aliases WHERE normalized_alias=?", (key,)).fetchone()
    if alias:
        rows = db.execute(
            "SELECT l.id FROM alias_ledger a JOIN ledger_accounts l ON l.id=a.ledger_id "
            "WHERE a.alias_id=? AND l.archived=0", (alias["id"],),
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    rows = db.execute(
        "SELECT s.ledger_id,s.habitual FROM supplier_ledger s JOIN ledger_accounts l ON l.id=s.ledger_id "
        "WHERE s.supplier_id=? AND l.archived=0 ORDER BY s.habitual DESC,l.code", (supplier_id,),
    ).fetchall()
    preferred = [r[0] for r in rows if r[1]]
    return preferred or [r[0] for r in rows]


def assign(db, movement_ids, ledger_id, *, remember=False, normalize=None):
    with db:
        db.execute("BEGIN IMMEDIATE")
        if ledger_id is not None and not db.execute(
            "SELECT 1 FROM ledger_accounts WHERE id=? AND archived=0", (ledger_id,)
        ).fetchone():
            raise ValueError("Conto contabile non disponibile")
        for identifier in set(movement_ids):
            old = db.execute("SELECT ledger_account_id,description FROM transactions WHERE id=?", (identifier,)).fetchone()
            if old is None:
                raise ValueError("Movimento non trovato")
            db.execute("UPDATE transactions SET ledger_account_id=? WHERE id=?", (ledger_id, identifier))
            db.execute("INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'ledger_account_id',?,?)",
                       (identifier, json.dumps(old[0]), json.dumps(ledger_id)))
            if remember:
                if ledger_id is None or normalize is None:
                    raise ValueError("Scegli un conto contabile per la regola futura")
                rule_key = normalize(old["description"])
                previous = db.execute("SELECT ledger_id FROM ledger_rules WHERE description=?",(rule_key,)).fetchone()
                db.execute("INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'regola_conto_contabile',?,?)",
                           (identifier,json.dumps(previous[0] if previous else None),json.dumps(ledger_id)))
                db.execute("INSERT INTO ledger_rules VALUES(?,?) ON CONFLICT(description) DO UPDATE SET ledger_id=excluded.ledger_id",
                           (normalize(old["description"]), ledger_id))


def report(db, year, month):
    from services.budget import period
    prefix = period(year, month)
    totals = {}
    for row in db.execute(
        "SELECT t.*,l.code,l.description AS ledger_description FROM transactions t "
        "LEFT JOIN ledger_accounts l ON l.id=t.ledger_account_id "
        "WHERE substr(t.occurred_at,1,7)=? AND t.status='COMPLETATO'", (prefix,)
    ):
        key = (row["ledger_account_id"], row["currency"])
        item = totals.setdefault(key, {"code": row["code"] if row["code"] is not None else "Non assegnato",
                                      "description": row["ledger_description"] or "", "currency":row["currency"],
                                      "actual":Decimal(0), "fees":Decimal(0), "budget":Decimal(0)})
        item["fees"] += Decimal(str(row["fee"]))
        if row["classification_status"] not in ("trasferimento","escluso") and row["accounting_nature"] not in (
            "trasferimento","prelievo","giroconto","escluso",
        ):
            item["actual"] += Decimal(str(row["amount"]))
    for row in db.execute("SELECT b.*,l.code,l.description FROM ledger_budgets b JOIN ledger_accounts l ON l.id=b.ledger_id WHERE year=? AND month=?", (year,month)):
        key = (row["ledger_id"],row["currency"])
        item = totals.setdefault(key, {"code":row["code"],"description":row["description"],"currency":row["currency"],
                                      "actual":Decimal(0),"fees":Decimal(0),"budget":Decimal(0)})
        item["budget"] = Decimal(row["amount_minor"])/100
    labels = {r["id"]:r["category_labels"] or "" for r in accounts(db,include_archived=True)}
    for (ledger_id,currency),item in totals.items():
        item["categories"] = labels.get(ledger_id,"")
    return list(totals.values())


def import_signature(db):
    queries = (
        "SELECT * FROM ledger_accounts ORDER BY id",
        "SELECT id,name FROM suppliers ORDER BY id",
        "SELECT id,name FROM categories ORDER BY id",
        "SELECT * FROM ledger_categories ORDER BY ledger_id,category_id",
        "SELECT * FROM supplier_ledger ORDER BY supplier_id,ledger_id",
    )
    return tuple(tuple(tuple(r) for r in db.execute(sql)) for sql in queries)


class LedgerService:
    def __init__(self, store):
        self.store = store
        self.db = store.db

    def accounts(self, search="", include_archived=False):
        return accounts(self.db, search, include_archived)

    def preview(self, records):
        return preview(self.db, records)

    def signature(self):
        return import_signature(self.db)

    def import_chart(self, records, source_name, expected=None):
        return import_chart(self.db, records, source_name, expected)

    def edit(self, identifier, description, archived):
        return edit_account(self.db, identifier, description, archived)

    def suppliers(self):
        return self.db.execute("SELECT id,name FROM suppliers WHERE archived=0 ORDER BY name").fetchall()

    def aliases(self, supplier_id):
        return self.db.execute("SELECT id,normalized_alias FROM supplier_aliases WHERE supplier_id=?", (supplier_id,)).fetchall()

    def associations(self, supplier_id, alias_id=None):
        if alias_id is not None:
            return [(r[0],0) for r in self.db.execute("SELECT ledger_id FROM alias_ledger WHERE alias_id=?", (alias_id,))]
        return [tuple(r) for r in self.db.execute("SELECT ledger_id,habitual FROM supplier_ledger WHERE supplier_id=?", (supplier_id,))]

    def associate(self, supplier_id, ids, habitual=None, alias_id=None):
        return associate(self.db, supplier_id, ids, habitual, alias_id)

    def assign(self, ids, ledger_id, remember=False):
        return assign(self.db, ids, ledger_id, remember=remember, normalize=self.store.normalize_description)

    def candidates(self, description, supplier_id):
        return candidates(self.store, description, supplier_id)

    def report(self, year, month):
        return report(self.db, year, month)

    def save_budget(self, year, month, ledger_id, currency, amount):
        from services.budget import period
        period(year, month)
        value = Decimal(str(amount).replace(",","."))
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError("Importo non valido. Usa massimo due decimali.")
        if currency not in ("EUR","CHF"):
            raise ValueError("Valuta non supportata")
        if not self.db.execute("SELECT 1 FROM ledger_accounts WHERE id=? AND archived=0", (ledger_id,)).fetchone():
            raise ValueError("Conto contabile non disponibile")
        with self.db:
            old = self.db.execute("SELECT amount_minor FROM ledger_budgets WHERE year=? AND month=? AND ledger_id=? AND currency=?",
                                  (year,month,ledger_id,currency)).fetchone()
            self.db.execute("INSERT INTO ledger_budgets VALUES(?,?,?,?,?) ON CONFLICT(year,month,ledger_id,currency) DO UPDATE SET amount_minor=excluded.amount_minor",
                            (year,month,ledger_id,currency,int(value*100)))
            self.db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                            (f"budget_conto:{year}:{month}:{ledger_id}:{currency}",str(old[0]) if old else None,str(value)))
