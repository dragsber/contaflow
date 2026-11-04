from datetime import date
from decimal import Decimal


STATUSES = {
    "classificato": "✓ Classificato", "proposto": "? Proposto",
    "in_attesa": "… In attesa", "trasferimento": "↔ Trasferimento interno",
    "escluso": "⊘ Escluso dal consuntivo",
}


def money(value, currency):
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    text = format(amount, ",.2f").translate(str.maketrans(",.", ".,"))
    return f"{text} {'€' if currency == 'EUR' else currency}"


def movements(db, account=None, *, search="", start="", end="", category=None,
              supplier=None, status="", sort="date", descending=True, ledger=None):
    ordering = {
        "ledger": "l.code",
        "date": "t.occurred_at", "description": "t.description COLLATE NOCASE",
        "amount": "t.amount", "fee": "t.fee", "currency": "t.currency",
        "kind": "t.kind", "classification": "t.classification_status",
        "supplier": "s.name", "category": "c.name", "account": "a.name",
    }
    if sort not in ordering:
        raise ValueError("Colonna di ordinamento non valida")
    for value in (start, end):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Usa date nel formato AAAA-MM-GG") from error
    if start and end and start > end:
        raise ValueError("Il periodo termina prima della data iniziale")
    conditions, args = [], []
    for condition, value in (
        ("a.name=?", account), ("substr(t.occurred_at,1,10)>=?", start),
        ("substr(t.occurred_at,1,10)<=?", end), ("t.category_id=?", category),
        ("t.supplier_id=?", supplier),
        ("t.ledger_account_id=?", ledger if ledger != "unassigned" else None),
    ):
        if value is not None and value != "":
            conditions.append(condition)
            args.append(value)
    if search:
        conditions.append(
            "instr(lower(t.description || ' ' || COALESCE(s.name,'') || ' ' || "
            "COALESCE(c.name,'')),lower(?))>0"
        )
        args.append(search.strip())
    if ledger == "unassigned":
        conditions.append("t.ledger_account_id IS NULL")
    if status == "da_classificare":
        conditions.append("t.classification_status IN ('in_attesa','proposto')")
    elif status:
        if status not in STATUSES:
            raise ValueError("Stato non valido")
        conditions.append("t.classification_status=?")
        args.append(status)
    sql = (
        "SELECT t.*,a.name AS account,s.name AS supplier,c.name AS category,l.code AS ledger_code "
        "FROM transactions t JOIN accounts a ON a.id=t.account_id "
        "LEFT JOIN suppliers s ON s.id=t.supplier_id "
        "LEFT JOIN categories c ON c.id=t.category_id "
        "LEFT JOIN ledger_accounts l ON l.id=t.ledger_account_id"
    )
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += f" ORDER BY {ordering[sort]} {'DESC' if descending else 'ASC'},t.id DESC"
    return db.execute(sql, args).fetchall()
