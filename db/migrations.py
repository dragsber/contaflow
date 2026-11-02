import sqlite3

LATEST_SCHEMA_VERSION = 1

def migrate(connection: sqlite3.Connection) -> None:
    """Record the current compatible schema version without changing user data."""
    connection.execute('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)')
    row = connection.execute('SELECT version FROM schema_version LIMIT 1').fetchone()
    if row is None:
        connection.execute('INSERT INTO schema_version(version) VALUES (?)', (LATEST_SCHEMA_VERSION,))
    elif row[0] < LATEST_SCHEMA_VERSION:
        connection.execute('UPDATE schema_version SET version=?', (LATEST_SCHEMA_VERSION,))
    connection.commit()
