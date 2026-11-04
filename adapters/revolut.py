import csv
import hashlib
import io
from math import isfinite
from datetime import datetime
from decimal import Decimal, InvalidOperation


def fingerprint(account, row):
    # Preserve Alpha 0.1 fingerprints. Float formatting is identity compatibility only.
    when = row.get("Data di completamento") or row["Data di inizio"]
    values = (account, when, row["Tipo"], row["Descrizione"], str(float(row["Importo"])),
              row["Valuta"].strip().upper(), str(float(row.get("Costo") or 0)))
    return hashlib.sha256("|".join(values).encode()).hexdigest()


def read_rows(payload):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    required = {"Tipo", "Data di inizio", "Descrizione", "Importo", "Valuta", "State"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Schema CSV Revolut non riconosciuto")
    rows = list(reader)
    for number, row in enumerate(rows, 2):
        if row.get("State", "").strip().upper() != "COMPLETATO":
            continue
        try:
            amount, fee = Decimal(row["Importo"]), Decimal(row.get("Costo") or "0")
            if not amount.is_finite() or not fee.is_finite() or fee < 0 or not isfinite(float(amount)) or not isfinite(float(fee)):
                raise ValueError("Importi o commissioni non validi")
            datetime.fromisoformat(row.get("Data di completamento") or row["Data di inizio"])
            if not row["Valuta"] or not row["Descrizione"]:
                raise ValueError("Valuta o descrizione mancante")
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError(f"Dati non validi alla riga {number}: {error}") from error
    return rows


def reconcile(rows):
    completed = []
    for number, row in enumerate(rows, 2):
        if row.get("State", "").strip().upper() != "COMPLETATO":
            continue
        if not row.get("Data di completamento") or not row.get("Saldo"):
            raise ValueError(f"Data o saldo mancante alla riga {number}")
        try:
            amount = Decimal(row["Importo"]) - Decimal(row.get("Costo") or "0")
            balance = Decimal(row["Saldo"])
            if not balance.is_finite():
                raise ValueError("Saldo non finito")
        except (InvalidOperation, ValueError) as error:
            raise ValueError(f"Saldo non valido alla riga {number}") from error
        completed.append((row["Data di completamento"], number, row["Valuta"].strip().upper(), amount, balance))
    previous, anomalies = {}, []
    for _, number, currency, amount, balance in sorted(completed):
        if currency in previous and balance - previous[currency] != amount:
            anomalies.append({"row": number, "currency": currency, "expected_delta": str(amount),
                              "actual_delta": str(balance - previous[currency])})
        previous[currency] = balance
    return anomalies
