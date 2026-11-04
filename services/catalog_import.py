import csv
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


COLUMNS = ("fornitore", "categoria", "tipo", "alias", "note")


def read_catalog(path):
    """Formato esplicito. Excel richiede il foglio Anagrafiche e le intestazioni COLUMNS."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
                raise ValueError("Intestazioni richieste: " + ";".join(COLUMNS))
            rows = list(reader)
    elif path.suffix.lower() == ".xlsx":
        with zipfile.ZipFile(path) as book:
            workbook = ET.fromstring(book.read("xl/workbook.xml"))
            sheet = next((s for s in workbook.findall(".//{*}sheet")
                          if s.get("name") == "Anagrafiche"), None)
            if sheet is None:
                raise ValueError("Manca il foglio strutturato Anagrafiche")
            relation_id = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
            relations = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
            target = next(r.get("Target") for r in relations if r.get("Id") == relation_id)
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            shared = []
            if "xl/sharedStrings.xml" in book.namelist():
                shared = ["".join(s.itertext()) for s in ET.fromstring(book.read("xl/sharedStrings.xml"))]
            matrix = []
            for xmlrow in ET.fromstring(book.read(target)).findall(".//{*}sheetData/{*}row"):
                cells = {}
                for cell in xmlrow:
                    letters = re.match("[A-Z]+", cell.get("r", "A")).group()
                    index = 0
                    for letter in letters:
                        index = index * 26 + ord(letter) - 64
                    value = cell.findtext("{*}v", "")
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("{*}is").itertext())
                    if cell.find("{*}f") is not None:
                        raise ValueError("Le anagrafiche devono contenere valori, senza formule")
                    cells[index - 1] = value
                matrix.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
            if not matrix or not set(COLUMNS).issubset(matrix[0]):
                raise ValueError("Intestazioni richieste: " + ";".join(COLUMNS))
            rows = [dict(zip(matrix[0], row + [""] * len(matrix[0]))) for row in matrix[1:]]
    else:
        raise ValueError("Seleziona CSV strutturato o XLSX con foglio Anagrafiche")
    result, names = [], set()
    for number, row in enumerate(rows, 2):
        record = {key: (row.get(key) or "").strip() for key in COLUMNS}
        if not any(record.values()):
            continue
        if not record["categoria"] or record["tipo"] not in ("entrata", "uscita", "trasferimento"):
            raise ValueError(f"Categoria o tipo non valido alla riga {number}")
        name = " ".join(record["fornitore"].upper().split())
        if name and name in names:
            raise ValueError(f"Fornitore duplicato alla riga {number}")
        if name:
            names.add(name)
        record["fornitore"] = name
        result.append(record)
    if not result:
        raise ValueError("Nessuna anagrafica da importare")
    return result


def import_catalog(db, records, normalize):
    with db:
        for row in records:
            category = db.execute("SELECT id,category_type FROM categories WHERE name=?",
                                  (row["categoria"],)).fetchone()
            if category and category[1] != row["tipo"]:
                raise ValueError("Tipo incompatibile per la categoria " + row["categoria"])
            category_id = category[0] if category else db.execute(
                "INSERT INTO categories(name,category_type) VALUES(?,?)",
                (row["categoria"], row["tipo"]),
            ).lastrowid
            if row["fornitore"]:
                if db.execute("SELECT 1 FROM suppliers WHERE name=?", (row["fornitore"],)).fetchone():
                    raise ValueError("Fornitore già presente: " + row["fornitore"])
                supplier = db.execute(
                    "INSERT INTO suppliers(name,habitual_category_id,notes) VALUES(?,?,?)",
                    (row["fornitore"], category_id, row["note"]),
                ).lastrowid
                if row["alias"]:
                    db.execute("INSERT INTO supplier_aliases(normalized_alias,supplier_id) VALUES(?,?)",
                               (normalize(row["alias"]), supplier))
    return len(records)
