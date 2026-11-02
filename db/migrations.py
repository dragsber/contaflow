import sqlite3

LATEST_SCHEMA_VERSION = 2


def _columns(connection, table):
    return {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}


def _add_column(connection, table, declaration):
    name = declaration.split()[0]
    if name not in _columns(connection, table):
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {declaration}')


def _migration_2(connection):
    connection.executescript("""
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


def migrate(connection: sqlite3.Connection) -> None:
    connection.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)')
    row = connection.execute('SELECT version FROM schema_version LIMIT 1').fetchone()
    version = row[0] if row else 0
    if version < 1:
        connection.execute('INSERT INTO schema_version(version) VALUES (1)')
        version = 1
    if version < 2:
        _migration_2(connection)
        connection.execute('UPDATE schema_version SET version=2')
    connection.commit()
