import sqlite3


SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_TIMEOUT_SECONDS = SQLITE_BUSY_TIMEOUT_MS / 1000


def connect_database(database, *, foreign_keys=False):
    conn = sqlite3.connect(database, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f'PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}')
    if foreign_keys:
        conn.execute('PRAGMA foreign_keys = ON')
    return conn


def enable_wal(conn):
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA synchronous = NORMAL')
