import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation


def period(year, month):
    try:
        date(int(year), int(month), 1)
    except (ValueError, TypeError) as error:
        raise ValueError("Anno o mese non valido") from error
    return f"{int(year):04d}-{int(month):02d}"


def save_budget(db, year, month, category_id, currency, amount):
    from db.migrations import schema_version
    if schema_version(db) >= 8:
        raise ValueError("I budget per categoria sono storici. Imposta il budget sulle sottovoci.")
    period(year, month)
    currency = currency.strip().upper()
    if currency not in ("EUR", "CHF"):
        raise ValueError("Valuta budget non supportata")
    try:
        amount = Decimal(str(amount).replace(",", "."))
        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Inserisci un importo positivo con massimo due decimali")
        minor = int(amount * 100)
        if minor > 9223372036854775807:
            raise ValueError("Importo troppo elevato")
    except InvalidOperation as error:
        raise ValueError("Importo non valido") from error
    category = db.execute("SELECT category_type FROM categories WHERE id=?", (category_id,)).fetchone()
    if category is None or category[0] == "trasferimento":
        raise ValueError("Scegli una categoria di entrata o uscita")
    with db:
        old = db.execute(
            "SELECT * FROM budgets WHERE year=? AND month=? AND category_id=? AND currency=?",
            (year, month, category_id, currency),
        ).fetchone()
        if old:
            db.execute("UPDATE budgets SET amount=?,amount_minor=? WHERE id=?", (str(amount), minor, old["id"]))
        else:
            db.execute(
                "INSERT INTO budgets(year,month,category_id,amount,currency,amount_minor) VALUES(?,?,?,?,?,?)",
                (year, month, category_id, str(amount), currency, minor),
            )
        db.execute(
            "INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
            (f"budget:{year}-{month}:{category_id}:{currency}",
             json.dumps(dict(old) if old else None), str(amount)),
        )


def budget_report(db, year, month):
    prefix = period(year, month)
    categories = {r["id"]: dict(r) for r in db.execute("SELECT id,name,category_type FROM categories")}
    plans, actual = {}, defaultdict(lambda: Decimal(0))
    totals = defaultdict(lambda: {key: Decimal(0) for key in (
        "planned_income", "planned_expenses", "income", "expenses", "fees", "unclassified",
    )})
    for row in db.execute("SELECT * FROM budgets WHERE year=? AND month=?", (year, month)):
        plans[(row["category_id"], row["currency"])] = (
            Decimal(row["amount_minor"]) / 100 if row["amount_minor"] is not None else Decimal(str(row["amount"]))
        )
    for row in db.execute(
        "SELECT * FROM transactions WHERE substr(occurred_at,1,7)=? AND status='COMPLETATO'", (prefix,)
    ):
        currency = row["currency"]
        amount, fee = Decimal(str(row["amount"])), Decimal(str(row["fee"]))
        totals[currency]["fees"] += fee
        if row["classification_status"] in ("trasferimento", "escluso") or row["accounting_nature"] in (
            "trasferimento", "prelievo", "giroconto", "escluso",
        ):
            continue
        category = categories.get(row["category_id"])
        if category is None:
            totals[currency]["unclassified"] += amount
            continue
        if category["category_type"] == "trasferimento":
            continue
        value = amount if category["category_type"] == "entrata" else -amount
        actual[(category["id"], currency)] += value
    rows = []
    for key in sorted(set(plans) | set(actual), key=lambda k:(categories[k[0]]["name"], k[1])):
        category_id, currency = key
        category = categories[category_id]
        planned, spent = plans.get(key, Decimal(0)), actual.get(key, Decimal(0))
        rows.append({"category_id":category_id, "category":category["name"], "type":category["category_type"],
                     "currency":currency, "planned":planned, "actual":spent, "difference":spent-planned})
        suffix = "income" if category["category_type"] == "entrata" else "expenses"
        totals[currency]["planned_"+suffix] += planned
        totals[currency][suffix] += spent
    return rows, dict(totals)
