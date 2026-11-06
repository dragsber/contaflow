"""Presentazione pura: non apre file, database o interfacce."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

PERIODS = ("Tutti i movimenti", "Questo mese", "Ultimi 30 giorni", "Anno corrente")
STATES = {
    "classificato": "✓ Classificato",
    "proposto": "? Proposto",
    "in_attesa": "… In attesa",
    "trasferimento": "↔ Trasferimento",
    "escluso": "⊘ Escluso",
}


def money(value, currency):
    """Formatta senza cambiare il valore sorgente, mantenendo EUR e CHF distinti."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    number = format(abs(amount), ",.2f").translate(str.maketrans(",.", ".,"))
    sign = "-" if amount < 0 else "+" if amount > 0 else ""
    return f"{sign}{number} {'€' if currency == 'EUR' else currency}"


def date_it(value):
    return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")


def period_bounds(label, today=None):
    today = today or date.today()
    if label == "Questo mese":
        return today.replace(day=1).isoformat(), today.isoformat()
    if label == "Ultimi 30 giorni":
        return (today - timedelta(days=29)).isoformat(), today.isoformat()
    if label == "Anno corrente":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    if label == "Tutti i movimenti":
        return "", ""
    raise ValueError("Periodo non previsto")


def row_matches(row, *, search="", account="Tutti i conti", status="Tutti gli stati", start="", end=""):
    if account != "Tutti i conti" and row["account"] != account:
        return False
    if status != "Tutti gli stati" and row["classification_status"] != status:
        return False
    day = str(row["occurred_at"])[:10]
    if start and day < start or end and day > end:
        return False
    text = " ".join(str(row.get(key) or "") for key in ("description", "supplier", "category", "subcategory"))
    return search.strip().casefold() in text.casefold()


def filter_rows(rows, **kwargs):
    return [row for row in rows if row_matches(row, **kwargs)]


def shown_count(shown, total):
    return f"{len(shown)} di {len(total)} movimenti"


def label_for_balance(summary, reconciliation):
    """La variazione netta non è un saldo bancario effettivo."""
    if summary.get("bank_balance") is None:
        return "Variazione netta dei movimenti", summary["balance"], "Non verificato"
    if reconciliation and reconciliation.get("status") == "confermata":
        return (f"Saldo riconciliato al {date_it(reconciliation['as_of'])}", summary["bank_balance"], "Riconciliato")
    return "Saldo calcolato", summary["bank_balance"], "Da riconciliare"


def currency_totals(summaries):
    result = {}
    for item in summaries:
        currency = item["currency"]
        result[currency] = result.get(currency, Decimal(0)) + Decimal(str(item["balance"]))
    return result
