"""Read-only workbook mapping. No personal workbook or inferred relationships."""
import csv
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET


def workbook_rows(path, sheet):
    if str(path).lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return [dict(zip((column_name(i) for i in range(len(row))), row))
                    for row in csv.reader(handle, delimiter=";")]
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        selected = next((s for s in workbook.findall(".//{*}sheet") if s.get("name") == sheet), None)
        if selected is None:
            raise ValueError("Foglio non trovato. Specifica il nome esatto del foglio.")
        identifier = next(v for k, v in selected.attrib.items() if k.endswith("}id"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == identifier)
        target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ["".join(t.text or "" for t in s.findall(".//{*}t"))
                      for s in ET.fromstring(book.read("xl/sharedStrings.xml"))]
        formats = {}
        styles = []
        if "xl/styles.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/styles.xml"))
            formats = {int(r.get("numFmtId")): r.get("formatCode") for r in root.findall(".//{*}numFmt")}
            styles = [int(r.get("numFmtId", "0")) for r in root.findall("{*}cellXfs/{*}xf")]
        rows = []
        for row in ET.fromstring(book.read(target)).findall(".//{*}sheetData/{*}row"):
            number = int(row.get("r", len(rows) + 1))
            while len(rows) < number:
                rows.append({})
            for cell in row:
                column = re.match("[A-Z]+", cell.get("r", "A")).group()
                value = cell.findtext("{*}v", "")
                if cell.find("{*}f") is not None:
                    rows[number-1][column] = None
                    continue
                if cell.get("t") == "s":
                    value = shared[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//{*}t"))
                elif value and styles:
                    fmt = formats.get(styles[int(cell.get("s", "0"))], "")
                    if re.fullmatch("0+", fmt) and re.fullmatch("[0-9]+", value):
                        value = value.zfill(len(fmt))
                    elif fmt and fmt != "General":
                        value = None
                rows[number-1][column] = value
        return rows


def column_name(index):
    result = ""
    while index >= 0:
        index, remainder = divmod(index, 26)
        result = chr(65 + remainder) + result
        index -= 1
    return result


def mapped_records(path, sheet, mapping, first_row=2):
    if not mapping.get("code") or not mapping.get("description") or first_row < 1:
        raise ValueError("Specifica colonne codice/descrizione e prima riga valida")
    records, errors = [], []
    for number, row in enumerate(workbook_rows(path, sheet), 1):
        if number < first_row:
            continue
        values = {key: row.get(column, "") if column else "" for key, column in mapping.items()}
        if not any(values.values()):
            continue
        if any(value is None for value in values.values()):
            errors.append(f"Riga {number}: formula o formato numerico ambiguo. Occorrono valori espliciti.")
        elif not values["code"] or not values["description"]:
            errors.append(f"Riga {number}: codice o descrizione mancante")
        else:
            records.append(values)
    if errors:
        raise ValueError("\n".join(errors))
    if not records:
        raise ValueError("Nessun conto contabile presente nella mappatura")
    return tuple(records)
