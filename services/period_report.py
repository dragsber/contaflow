import calendar
from datetime import date, timedelta
from decimal import Decimal


def report(db, start, end):
    try:
        start, end = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError) as error:
        raise ValueError("Inserisci date nel formato AAAA-MM-GG") from error
    if start > end:
        raise ValueError("La data iniziale deve precedere quella finale")
    result = {}
    month = start.replace(day=1)
    months = set()
    planned_months = {}
    while month <= end:
        months.add((month.year, month.month))
        last_day = calendar.monthrange(month.year, month.month)[1]
        last = month.replace(day=last_day)
        included_days = (min(end, last) - max(start, month)).days + 1
        for row in db.execute(
            "SELECT b.*,l.code,l.description FROM ledger_budgets b JOIN ledger_accounts l "
            "ON l.id=b.ledger_id WHERE b.year=? AND b.month=?", (month.year, month.month)
        ):
            key = (row["ledger_id"], row["currency"])
            planned_months.setdefault(key, set()).add((month.year, month.month))
            item = result.setdefault(key, dict(code=row["code"], description=row["description"],
                                               currency=row["currency"], budget=Decimal(0),
                                               actual=Decimal(0), fees=Decimal(0)))
            item["budget"] += Decimal(row["amount_minor"]) / 100 * included_days / last_day
        month = last + timedelta(days=1)
    for row in db.execute(
        "SELECT t.*,l.code,l.description AS ledger_description FROM transactions t "
        "LEFT JOIN ledger_accounts l ON l.id=t.ledger_account_id "
        "WHERE substr(t.occurred_at,1,10) BETWEEN ? AND ? AND t.status='COMPLETATO'",
        (start.isoformat(), end.isoformat()),
    ):
        key = (row["ledger_account_id"], row["currency"])
        item = result.setdefault(key, dict(code=row["code"] if row["code"] is not None else "Non assegnato",
                                           description=row["ledger_description"] or "", currency=row["currency"],
                                           budget=Decimal(0), actual=Decimal(0), fees=Decimal(0)))
        item["fees"] += Decimal(str(row["fee"]))
        if row["classification_status"] not in ("trasferimento", "escluso") and row["accounting_nature"] not in (
            "trasferimento", "prelievo", "giroconto", "escluso",
        ):
            item["actual"] += Decimal(str(row["amount"]))
    for key, item in result.items():
        item["budget"] = item["budget"].quantize(Decimal("0.01"))
        item["difference"] = item["actual"] - item["budget"]
        item["missing_months"] = len(months - planned_months.get(key, set()))
    return sorted(result.values(), key=lambda item: (item["code"], item["currency"]))
