import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

LATEST_SCHEMA_VERSION = 4


def _columns(connection, table):
    return {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}


def _add_column(connection, table, declaration):
    name = declaration.split()[0]
    if name not in _columns(connection, table):
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {declaration}')


def _migration_2(connection):
    _execute_statements(connection, """
    CREATE TABLE IF NOT EXISTS importations (
        id INTEGER PRIMARY KEY,
        file_name TEXT NOT NULL,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        result TEXT NOT NULL DEFAULT 'completed'
    );
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        habitual_category_id INTEGER REFERENCES categories(id),
        archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
    );
    CREATE TABLE IF NOT EXISTS supplier_aliases (
        id INTEGER PRIMARY KEY,
        normalized_alias TEXT NOT NULL UNIQUE,
        supplier_id INTEGER NOT NULL REFERENCES suppliers(id)
    );
    CREATE TABLE IF NOT EXISTS classification_rules (
        id INTEGER PRIMARY KEY,
        exact_description TEXT NOT NULL UNIQUE,
        supplier_id INTEGER REFERENCES suppliers(id),
        category_id INTEGER REFERENCES categories(id),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1))
    );
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY,
        movement_out_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
        movement_in_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
        exchange_rate REAL
    );
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY,
        refund_movement_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
        original_movement_id INTEGER NOT NULL REFERENCES transactions(id),
        amount REAL NOT NULL CHECK (amount >= 0)
    );
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY,
        year INTEGER NOT NULL,
        month INTEGER CHECK (month BETWEEN 1 AND 12),
        category_id INTEGER NOT NULL REFERENCES categories(id),
        amount REAL NOT NULL CHECK (amount >= 0),
        currency TEXT NOT NULL,
        CHECK (month IS NULL OR month BETWEEN 1 AND 12)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_budget_period
        ON budgets(year, COALESCE(month, 0), category_id, currency);
    CREATE TABLE IF NOT EXISTS opening_balances (
        id INTEGER PRIMARY KEY,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        as_of TEXT NOT NULL,
        amount REAL NOT NULL,
        confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0,1)),
        UNIQUE(account_id, as_of)
    );
    """)
    _add_column(connection, 'categories',
                "category_type TEXT NOT NULL DEFAULT 'uscita'")
    _add_column(connection, 'categories',
                "is_custom INTEGER NOT NULL DEFAULT 1")
    _add_column(connection, 'categories',
                "archived INTEGER NOT NULL DEFAULT 0")
    _add_column(connection, 'transactions',
                "supplier_id INTEGER REFERENCES suppliers(id)")
    _add_column(connection, 'transactions',
                "classification_status TEXT NOT NULL DEFAULT 'in_attesa'")
    _add_column(connection, 'transactions',
                "classification_origin TEXT")
    _add_column(connection, 'transactions',
                "importation_id INTEGER REFERENCES importations(id)")
    connection.execute("""
        CREATE VIEW IF NOT EXISTS movimenti AS
        SELECT id, account_id, occurred_at, description, amount, currency,
               fee, kind, status, supplier_id, category_id,
               classification_status, classification_origin, importation_id,
               source_json
        FROM transactions
    """)


def _migration_3(connection):
    _add_column(connection, 'supplier_aliases',
                "confirmed INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0,1))")


class MigrationError(RuntimeError):
    pass


def schema_version(connection):
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if not exists:
        return 0
    row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    return row[0] if row else 0


def _execute_statements(connection, script):
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("Migrazione SQL incompleta")


def backup_before_upgrade(connection):
    version = schema_version(connection)
    if version > LATEST_SCHEMA_VERSION:
        raise MigrationError("Database creato con una versione più recente di ContaFlow")
    if version == LATEST_SCHEMA_VERSION:
        return None
    tables = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1"
    ).fetchone()
    path = connection.execute("PRAGMA database_list").fetchone()[2]
    if not tables:
        return None
    if not path:
        raise MigrationError("Migrazione di database esistente in memoria non supportata")
    folder = Path(path).parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"ContaFlow_pre_migrazione_v{version}_{datetime.now():%Y%m%d_%H%M%S_%f}.sqlite3"
    try:
        with closing(sqlite3.connect(target)) as backup:
            connection.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise sqlite3.DatabaseError("Copia di sicurezza non integra")
    except Exception as error:
        raise MigrationError(
            f"Migrazione non avviata. Verifica della copia di sicurezza fallita: {target}"
        ) from error
    return str(target)


def _migration_4(connection):
    _add_column(connection, "transactions", "notes TEXT NOT NULL DEFAULT ''")
    _add_column(connection, "transactions", "accounting_nature TEXT NOT NULL DEFAULT 'ordinario'")


def migrate(connection: sqlite3.Connection, *, new_database=False) -> None:
    if connection.in_transaction:
        raise MigrationError("Completa la transazione prima di aggiornare il database")
    version = schema_version(connection)
    if version > LATEST_SCHEMA_VERSION:
        raise MigrationError("Database creato con una versione più recente di ContaFlow")
    migrations = {1: lambda db: None, 2: _migration_2, 3: _migration_3, 4: _migration_4}
    for target_version in range(version + 1, LATEST_SCHEMA_VERSION + 1):
        safety = None if new_database else backup_before_upgrade(connection)
        previous = schema_version(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            migrations[target_version](connection)
            connection.execute("DELETE FROM schema_version")
            connection.execute("INSERT INTO schema_version(version) VALUES (?)", (target_version,))
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("Controllo di integrità della migrazione fallito")
            connection.commit()
        except Exception as error:
            connection.rollback()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            actual = schema_version(connection)
            raise MigrationError(
                f"Aggiornamento database interrotto alla versione {target_version}. "
                f"Integrità dopo rollback: {integrity}. Versione attesa {previous}, rilevata {actual}. "
                f"Copia precedente: {safety or 'database nuovo senza dati utente'}"
            ) from error
