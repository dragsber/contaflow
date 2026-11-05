import calendar
import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction


def create(db, category_id, name, generic=False, ledger_account_id=None):
    if not name.strip():
        raise ValueError("Inserisci il nome della sottovoce")
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        category = db.execute("SELECT category_type FROM categories WHERE id=? AND archived=0", (category_id,)).fetchone()
        if not category or category[0] == "trasferimento":
            raise ValueError("Seleziona una categoria attiva di entrata o uscita")
        if generic and db.execute("SELECT 1 FROM subcategories WHERE category_id=? AND generic=1", (category_id,)).fetchone():
            raise ValueError("Esiste già una sottovoce generica per questa categoria")
        if ledger_account_id is not None and not db.execute(
            "SELECT 1 FROM ledger_accounts WHERE id=? AND archived=0 AND origin='importato'", (ledger_account_id,)
        ).fetchone():
            raise ValueError("Seleziona un conto contabile importato e attivo")
        return db.execute(
            "INSERT INTO subcategories(category_id,name,generic,ledger_account_id) VALUES(?,?,?,?)",
            (category_id, name, int(generic), ledger_account_id),
        ).lastrowid


def edit(db, identifier, name, ledger_account_id):
    if not name.strip():
        raise ValueError("Inserisci il nome della sottovoce")
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT name,ledger_account_id FROM subcategories WHERE id=?", (identifier,)).fetchone()
        if old is None:
            raise ValueError("Sottovoce non trovata")
        if ledger_account_id is not None and ledger_account_id != old["ledger_account_id"] and not db.execute(
            "SELECT 1 FROM ledger_accounts WHERE id=? AND archived=0 AND origin='importato'", (ledger_account_id,)
        ).fetchone():
            raise ValueError("Seleziona un conto contabile importato e attivo")
        db.execute("UPDATE subcategories SET name=?,ledger_account_id=? WHERE id=?", (name,ledger_account_id,identifier))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"sottovoce:{identifier}",json.dumps(tuple(old)),json.dumps([name,ledger_account_id])))


def save_budget(db, identifier, year, month, currency, amount):
    date(int(year), int(month), 1)
    if currency not in ("EUR", "CHF"):
        raise ValueError("Seleziona EUR o CHF")
    try:
        value = Decimal(str(amount).replace(",", "."))
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError("Importo non valido")
        minor = int(value * 100)
        if abs(minor) > 9223372036854775807:
            raise ValueError("Importo troppo elevato")
    except InvalidOperation as error:
        raise ValueError("Importo non valido") from error
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        category = db.execute(
            "SELECT c.category_type FROM subcategories s JOIN categories c ON c.id=s.category_id WHERE s.id=? AND s.archived=0 AND c.archived=0",
            (identifier,),
        ).fetchone()
        if not category or category[0] not in ("uscita","entrata"):
            raise ValueError("Sottovoce non disponibile")
        if (category[0] == "uscita" and value > 0) or (category[0] == "entrata" and value < 0):
            raise ValueError("Usa importi negativi per uscite e positivi per entrate")
        old = db.execute(
            "SELECT amount_minor FROM subcategory_budgets WHERE subcategory_id=? AND year=? AND month=? AND currency=?",
            (identifier, year, month, currency),
        ).fetchone()
        db.execute(
            "INSERT INTO subcategory_budgets VALUES(?,?,?,?,?) ON CONFLICT(subcategory_id,year,month,currency) "
            "DO UPDATE SET amount_minor=excluded.amount_minor",
            (identifier, year, month, currency, minor),
        )
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"budget_sottovoce:{identifier}:{year}:{month}:{currency}", str(old[0]) if old else None, str(minor)))


def assign(db, movement_ids, subcategory_id, *, remember=False, normalize=None):
    ids = list(dict.fromkeys(movement_ids))
    if not ids:
        raise ValueError("Seleziona almeno un movimento")
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        selected = None
        if subcategory_id is not None:
            selected = db.execute("SELECT * FROM subcategories WHERE id=? AND archived=0", (subcategory_id,)).fetchone()
            if selected is None:
                raise ValueError("Sottovoce non disponibile")
        for identifier in ids:
            old = db.execute("SELECT category_id,subcategory_id,description,classification_status,classification_origin FROM transactions WHERE id=?", (identifier,)).fetchone()
            if old is None:
                raise ValueError("Movimento non trovato")
            if selected and old["category_id"] != selected["category_id"]:
                raise ValueError("La sottovoce deve appartenere alla categoria del movimento")
            db.execute("UPDATE transactions SET subcategory_id=? WHERE id=?", (subcategory_id, identifier))
            db.execute("INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'subcategory_id',?,?)",
                       (identifier, json.dumps(old["subcategory_id"]), json.dumps(subcategory_id)))
            if selected and old["classification_status"] in ("in_attesa","proposto"):
                db.execute("UPDATE transactions SET classification_status='classificato',classification_origin='manuale' WHERE id=?", (identifier,))
                for field, value in (("classification_status","classificato"),("classification_origin","manuale")):
                    if old[field] != value:
                        db.execute("INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,?,?,?)",
                                   (identifier,field,json.dumps(old[field]),json.dumps(value)))
            if remember:
                if selected is None or normalize is None:
                    raise ValueError("Seleziona una sottovoce per la regola futura")
                key = normalize(old["description"])
                previous = db.execute("SELECT subcategory_id FROM subcategory_rules WHERE description=?", (key,)).fetchone()
                db.execute("INSERT INTO subcategory_rules VALUES(?,?) ON CONFLICT(description) DO UPDATE SET subcategory_id=excluded.subcategory_id",
                           (key,subcategory_id))
                db.execute("INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'regola_sottovoce',?,?)",
                           (identifier,json.dumps(previous[0] if previous else None),json.dumps(subcategory_id)))


def candidates(store, description, supplier_id):
    db = store.db
    key = store.normalize_description(description)
    rule = db.execute(
        "SELECT r.subcategory_id FROM subcategory_rules r JOIN subcategories s ON s.id=r.subcategory_id "
        "JOIN categories c ON c.id=s.category_id WHERE r.description=? AND s.archived=0 AND c.archived=0", (key,)
    ).fetchone()
    if rule:
        return [rule[0]]
    alias = db.execute("SELECT id FROM supplier_aliases WHERE normalized_alias=?", (key,)).fetchone()
    if alias:
        rows = db.execute(
            "SELECT a.subcategory_id FROM alias_subcategories a JOIN subcategories s ON s.id=a.subcategory_id "
            "JOIN categories c ON c.id=s.category_id WHERE a.alias_id=? AND s.archived=0 AND c.archived=0",(alias[0],)
        ).fetchall()
        if rows:
            return [r[0] for r in rows]
    rows = db.execute(
        "SELECT a.subcategory_id,a.habitual FROM supplier_subcategories a JOIN subcategories s ON s.id=a.subcategory_id "
        "JOIN categories c ON c.id=s.category_id WHERE a.supplier_id=? AND s.archived=0 AND c.archived=0",(supplier_id,)
    ).fetchall()
    preferred = [r[0] for r in rows if r[1]]
    return preferred or [r[0] for r in rows]


def archive(db, identifier, archived):
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso")
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT archived FROM subcategories WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("Sottovoce non trovata")
        db.execute("UPDATE subcategories SET archived=? WHERE id=?", (int(archived), identifier))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"sottovoce:{identifier}:archiviata",str(row[0]),str(int(archived))))


def associate(db, supplier_id, ids, habitual=None, alias_id=None):
    ids = set(ids)
    if habitual is not None and habitual not in ids:
        raise ValueError("La sottovoce abituale deve essere associata")
    with db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM suppliers WHERE id=? AND archived=0",(supplier_id,)).fetchone():
            raise ValueError("Fornitore non disponibile")
        for identifier in ids:
            if not db.execute("SELECT 1 FROM subcategories WHERE id=? AND archived=0",(identifier,)).fetchone():
                raise ValueError("Sottovoce non disponibile")
        if alias_id is not None:
            if not db.execute("SELECT 1 FROM supplier_aliases WHERE id=? AND supplier_id=?",(alias_id,supplier_id)).fetchone():
                raise ValueError("Alias non appartenente al fornitore")
            old = [tuple(r) for r in db.execute("SELECT * FROM alias_subcategories WHERE alias_id=?",(alias_id,))]
            db.execute("DELETE FROM alias_subcategories WHERE alias_id=?",(alias_id,))
            for identifier in ids:
                db.execute("INSERT INTO alias_subcategories VALUES(?,?)",(alias_id,identifier))
        else:
            old = [tuple(r) for r in db.execute("SELECT * FROM supplier_subcategories WHERE supplier_id=?",(supplier_id,))]
            db.execute("DELETE FROM supplier_subcategories WHERE supplier_id=?",(supplier_id,))
            for identifier in ids:
                db.execute("INSERT INTO supplier_subcategories VALUES(?,?,?)",(supplier_id,identifier,int(identifier==habitual)))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"associazioni_sottovoci:{supplier_id}:{alias_id}",json.dumps(old),json.dumps({"ids":sorted(ids),"abituale":habitual})))


def allocate_legacy(db, category_id, year, month, currency, allocations):
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM budgets WHERE category_id=? AND year=? AND month=? AND currency=?",
                         (category_id,year,month,currency)).fetchone()
        if old is None:
            raise ValueError("Budget legacy non disponibile")
        amount = Decimal(old["amount_minor"])/100 if old["amount_minor"] is not None else Decimal(str(old["amount"]))
        values = {}
        for identifier, value in allocations.items():
            value = Decimal(str(value).replace(",","."))
            if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
                raise ValueError("Importi non validi")
            if not db.execute("SELECT 1 FROM subcategories WHERE id=? AND category_id=? AND archived=0",
                              (identifier,category_id)).fetchone():
                raise ValueError("Sottovoce incompatibile")
            values[identifier] = int(value*100)
        if not values or sum(values.values()) != amount * 100:
            raise ValueError("La somma deve coincidere con il budget legacy")
        if db.execute("SELECT 1 FROM subcategory_budgets b JOIN subcategories s ON s.id=b.subcategory_id "
                      "WHERE s.category_id=? AND b.year=? AND b.month=? AND b.currency=?",
                      (category_id,year,month,currency)).fetchone():
            raise ValueError("Sono già presenti budget per sottovoce nel periodo")
        category_type = db.execute("SELECT category_type FROM categories WHERE id=?",(category_id,)).fetchone()[0]
        sign = 1 if category_type == "entrata" else -1
        for identifier, minor in values.items():
            db.execute("INSERT INTO subcategory_budgets VALUES(?,?,?,?,?)",(identifier,year,month,currency,sign*minor))
        db.execute("INSERT INTO legacy_allocations VALUES(?,?,?,?)",(category_id,year,month,currency))
        db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                   (f"ripartizione_legacy:{category_id}:{year}:{month}:{currency}",str(amount),json.dumps(values)))


def rounded(value):
    scaled, remainder = divmod(abs(value.numerator) * 100, value.denominator)
    if remainder * 2 >= value.denominator:
        scaled += 1
    sign = "-" if value.numerator < 0 and scaled else ""
    return Decimal(f"{sign}{scaled // 100}.{scaled % 100:02d}")


def report(db, start, end):
    if db.in_transaction:
        raise ValueError("Completa la transazione in corso prima del confronto")
    db.execute("BEGIN")
    try:
        return _report(db,start,end)
    finally:
        db.rollback()


def _report(db, start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end:
        raise ValueError("La data iniziale deve precedere quella finale")
    categories = {r["id"]: dict(r) for r in db.execute("SELECT id,name,category_type FROM categories")}
    subs = {r["id"]: dict(r) for r in db.execute(
        "SELECT s.*,l.code FROM subcategories s LEFT JOIN ledger_accounts l ON l.id=s.ledger_account_id"
    )}
    keys = {(s["category_id"],s["id"],currency) for s in subs.values() if not s["archived"] for currency in ("EUR","CHF")}
    actual, plans, selected, flags, legacy_info, legacy_used = {}, {}, {}, {}, {}, {}
    month = start.replace(day=1)
    months, covered = set(), {}
    while month <= end:
        month_key = (month.year,month.month)
        months.add(month_key)
        days = calendar.monthrange(month.year, month.month)[1]
        last = month.replace(day=days)
        fraction = Fraction((min(end, last)-max(start, month)).days+1, days)
        legacy = {(r["category_id"], r["currency"]): r for r in db.execute(
            "SELECT * FROM budgets WHERE year=? AND month=?", (month.year, month.month))}
        budgets = {(r["subcategory_id"], r["currency"]): r for r in db.execute(
            "SELECT * FROM subcategory_budgets WHERE year=? AND month=?", (month.year, month.month))}
        pairs = set(legacy) | {(subs[sid]["category_id"], currency) for sid, currency in budgets if sid in subs}
        for category_id, currency in pairs:
            category = categories[category_id]
            sign = 1 if category["category_type"] == "entrata" else -1
            members = [s for s in subs.values() if s["category_id"] == category_id and not s["archived"]]
            keys.update((category_id, s["id"], currency) for s in members)
            configured = [s for s in subs.values() if s["category_id"] == category_id and (s["id"], currency) in budgets]
            old = legacy.get((category_id, currency))
            group = (category_id, currency)
            covered.setdefault(group,set()).add(month_key)
            if old is not None:
                amount = Decimal(old["amount_minor"])/100 if old["amount_minor"] is not None else Decimal(str(old["amount"]))
                legacy_info[group] = legacy_info.get(group, Fraction()) + Fraction(amount)*sign*fraction
            if configured:
                selected[group] = selected.get(group, Fraction()) + sum(
                    (Fraction(budgets[(s["id"], currency)]["amount_minor"], 100)*fraction for s in configured), Fraction())
                if old is not None:
                    allocated = db.execute("SELECT 1 FROM legacy_allocations WHERE category_id=? AND year=? AND month=? AND currency=?",
                                           (category_id,month.year,month.month,currency)).fetchone()
                    flags.setdefault(group, set()).add("legacy ripartito" if allocated else "Conflitto legacy")
                if any((s["id"], currency) not in budgets for s in members):
                    flags.setdefault(group, set()).add("Budget parziale: alcune sottovoci non hanno un importo impostato")
                for s in configured:
                    key = (category_id, s["id"], currency)
                    keys.add(key)
                    plans[key] = plans.get(key, Fraction()) + Fraction(budgets[(s["id"],currency)]["amount_minor"], 100)*fraction
            elif old is not None:
                selected[group] = selected.get(group, Fraction()) + Fraction(amount)*sign*fraction
                legacy_used[group] = legacy_used.get(group, Fraction()) + Fraction(amount)*sign*fraction
                flags.setdefault(group, set()).add("legacy")
        if last >= end:
            break
        month = last + timedelta(days=1)
    for group in selected:
        if covered.get(group,set()) != months:
            flags.setdefault(group,set()).add("Budget non impostato per alcuni mesi")
    for row in db.execute(
        "SELECT category_id,subcategory_id,currency,amount FROM transactions WHERE status='COMPLETATO' "
        "AND substr(occurred_at,1,10) BETWEEN ? AND ? AND classification_status NOT IN ('trasferimento','escluso') "
        "AND accounting_nature NOT IN ('trasferimento','prelievo','giroconto','escluso')",
        (start.isoformat(), end.isoformat()),
    ):
        if row["category_id"] not in categories:
            continue
        if categories[row["category_id"]]["category_type"] == "trasferimento":
            continue
        key = (row["category_id"], row["subcategory_id"], row["currency"])
        keys.add(key)
        actual[key] = actual.get(key, Decimal(0)) + Decimal(str(row["amount"]))
    rows, groups = [], {}
    for category_id, sub_id, currency in sorted(keys, key=lambda k: (categories[k[0]]["name"], k[2], k[1] or 0)):
        key, group = (category_id, sub_id, currency), (category_id, currency)
        category, sub = categories[category_id], subs.get(sub_id)
        amount = actual.get(key, Decimal(0))
        budget = plans.get(key)
        rows.append({"type": "dettaglio" if sub else "non_ripartito", "category_id": category_id,
                     "category": category["name"], "subcategory_id": sub_id,
                     "subcategory": sub["name"] if sub else "Non ripartito", "code": sub["code"] if sub else None,
                     "currency": currency, "budget_exact": budget, "actual": amount})
        groups[group] = groups.get(group, Decimal(0)) + amount
    for group in selected:
        groups.setdefault(group,Decimal(0))
    for (category_id, currency), actual_sum in groups.items():
        budget = selected.get((category_id, currency))
        rows.append({"type": "subtotale_categoria", "category_id": category_id,
                     "category": categories[category_id]["name"], "subcategory": "", "code": None,
                     "currency": currency, "budget_exact": budget, "actual": actual_sum,
                     "warning": "; ".join(sorted(flags.get((category_id, currency), set()))),
                     "legacy_exact": legacy_info.get((category_id, currency))})
    for row in rows:
        value = row["budget_exact"]
        actual_exact = row["actual"]
        row["budget"] = rounded(value) if value is not None else None
        row["actual"] = actual_exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        row["difference"] = rounded(Fraction(actual_exact)-value) if value is not None else None
        if row["difference"] is not None:
            is_income = categories[row["category_id"]]["category_type"] == "entrata"
            if row["difference"] == 0:
                row["meaning"] = "in linea"
            else:
                row["meaning"] = ("sopra budget" if row["difference"] > 0 else "sotto budget") if is_income else ("risparmio" if row["difference"] > 0 else "sforamento")
        if row.get("legacy_exact") is not None:
            row["legacy"] = rounded(row["legacy_exact"])
            row["warning"] = (row.get("warning","") + f" · Budget legacy informativo: {str(row['legacy']).replace('.',',')}").strip(" ·")
        if row["type"] == "subtotale_categoria":
            detail = [r for r in rows if r["type"] in ("dettaglio","non_ripartito") and r["category_id"] == row["category_id"] and r["currency"] == row["currency"] and r["budget"] is not None]
            legacy = legacy_used.get((row["category_id"],row["currency"]))
            displayed_legacy = rounded(legacy) if legacy is not None else Decimal(0)
            row["rounding_difference"] = row["budget"] - sum((r["budget"] for r in detail), Decimal(0)) - displayed_legacy if row["budget"] is not None else Decimal(0)
            all_detail = [r for r in rows if r["type"] in ("dettaglio","non_ripartito") and r["category_id"] == row["category_id"] and r["currency"] == row["currency"]]
            row["rounding_actual"] = row["actual"] - sum((r["actual"] for r in all_detail),Decimal(0))
            if row["difference"] is not None and all(r["difference"] is not None for r in all_detail):
                row["rounding_delta"] = row["difference"] - sum((r["difference"] for r in all_detail),Decimal(0))
    return rows
