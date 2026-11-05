import csv
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


COLUMNS = ("fornitore", "categoria", "tipo", "alias", "note")


def read_catalog(path, *, sheet_name="Anagrafiche", header_row=1, mapping=None):
    """Formato esplicito. Excel richiede il foglio Anagrafiche e le intestazioni COLUMNS."""
    path = Path(path)
    if mapping is not None and (path.suffix.lower() != ".xlsx" or header_row < 1
                                or not mapping or min(mapping.values()) < 1
                                or len(set(mapping.values())) != len(mapping)):
        raise ValueError("Indica colonne XLSX distinte e positive e una riga di intestazione valida")
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
                          if s.get("name") == sheet_name), None)
            if sheet is None:
                raise ValueError(f"Foglio non trovato: {sheet_name}")
            relation_id = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
            relations = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
            target = next(r.get("Target") for r in relations if r.get("Id") == relation_id)
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            shared = []
            if "xl/sharedStrings.xml" in book.namelist():
                shared = ["".join(s.itertext()) for s in ET.fromstring(book.read("xl/sharedStrings.xml"))]
            matrix = []
            for index, xmlrow in enumerate(ET.fromstring(book.read(target)).findall(".//{*}sheetData/{*}row"), 1):
                row_number = int(xmlrow.get("r", index))
                if row_number < header_row:
                    continue
                cells = {}
                for cell in xmlrow:
                    letters = re.match("[A-Z]+", cell.get("r", "A")).group()
                    index = 0
                    for letter in letters:
                        index = index * 26 + ord(letter) - 64
                    if mapping is not None and index not in mapping.values():
                        continue
                    value = cell.findtext("{*}v", "")
                    if cell.get("t") == "s":
                        value = shared[int(value)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(cell.find("{*}is").itertext())
                    if cell.find("{*}f") is not None:
                        raise ValueError("Le anagrafiche devono contenere valori, senza formule")
                    cells[index - 1] = value
                matrix.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
            if mapping is not None:
                if not matrix or "fornitore" not in mapping or any(
                    column > len(matrix[0]) or not matrix[0][column - 1].strip() for column in mapping.values()
                ):
                    raise ValueError("Intestazione o colonna fornitore mancante")
                return [
                    {key: row[column - 1].strip() if len(row) >= column else ""
                     for key, column in mapping.items()}
                    for row in matrix[1:] if any(value.strip() for value in row)
                ]
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


def association_plan(db, records, normalize):
    """Plan only additive inserts; existing names and associations stay untouched."""
    suppliers = {row["name"].casefold(): row for row in db.execute("SELECT * FROM suppliers")}
    aliases = {row["normalized_alias"]: row["name"].casefold() for row in db.execute(
        "SELECT a.normalized_alias,s.name FROM supplier_aliases a JOIN suppliers s ON s.id=a.supplier_id"
    )}
    plan = []
    links = set()
    category_links = set()
    new_habitual = {}
    for number, row in enumerate(records, 1):
        name = " ".join(row["fornitore"].split()).upper()
        if not name:
            raise ValueError(f"Fornitore mancante nella riga dati {number}")
        key = name.casefold()
        supplier = suppliers.get(key)
        if supplier is not None and supplier["archived"]:
            raise ValueError(f"Fornitore archiviato nella riga dati {number}")
        category_name = row.get("categoria", "")
        category = None
        if category_name:
            category = db.execute("SELECT id FROM categories WHERE name=? AND archived=0", (category_name,)).fetchone()
            if category is None:
                raise ValueError(f"Categoria attiva non trovata nella riga dati {number}")
        if key not in suppliers:
            plan.append(("fornitore", name, row.get("note", ""), category[0] if category else None))
            suppliers[key] = None
            new_habitual[key] = category[0] if category else None
        elif supplier is not None:
            name = supplier["name"]
        if category:
            link = (key, category[0])
            if link not in category_links and (new_habitual.get(key) != category[0] if supplier is None else (
                supplier["habitual_category_id"] != category[0] and db.execute(
                    "SELECT 1 FROM supplier_categories WHERE supplier_id=? AND category_id=?",
                    (supplier["id"], category[0]),
                ).fetchone() is None
            )):
                plan.append(("categoria", name, category_name, category[0]))
                category_links.add(link)
        alias = normalize(row.get("alias", ""))
        if alias:
            if alias in aliases and aliases[alias] != key:
                raise ValueError(f"Alias in conflitto nella riga dati {number}")
            if alias not in aliases:
                plan.append(("alias", name, alias, None))
                aliases[alias] = key
        sub_name = row.get("sottovoce", "")
        if sub_name:
            if category is None:
                raise ValueError(f"Indica la categoria della sottovoce nella riga dati {number}")
            sub = db.execute("SELECT id FROM subcategories WHERE category_id=? AND name=? AND archived=0",
                             (category[0], sub_name)).fetchone()
            if sub is None:
                raise ValueError(f"Sottovoce attiva non trovata nella riga dati {number}")
            link = (key, sub[0])
            if link not in links and (supplier is None or db.execute(
                "SELECT 1 FROM supplier_subcategories WHERE supplier_id=? AND subcategory_id=?",
                (supplier["id"], sub[0]),
            ).fetchone() is None):
                plan.append(("sottovoce", name, sub_name, sub[0]))
                links.add(link)
    return plan


def apply_associations(db, records, normalize, preview):
    with db:
        db.execute("BEGIN IMMEDIATE")
        if association_plan(db, records, normalize) != preview:
            raise ValueError("Le anagrafiche sono cambiate. Ripeti l'anteprima.")
        for kind, name, value, identifier in preview:
            if kind == "fornitore":
                db.execute("INSERT INTO suppliers(name,notes,habitual_category_id) VALUES(?,?,?)",
                           (name, value, identifier))
            elif kind == "alias":
                db.execute("INSERT INTO supplier_aliases(normalized_alias,supplier_id) "
                           "SELECT ?,id FROM suppliers WHERE name=?", (value, name))
            elif kind == "categoria":
                db.execute("INSERT INTO supplier_categories(supplier_id,category_id) "
                           "SELECT id,? FROM suppliers WHERE name=?", (identifier, name))
            else:
                db.execute("INSERT INTO supplier_subcategories(supplier_id,subcategory_id) "
                           "SELECT id,? FROM suppliers WHERE name=?", (identifier, name))
