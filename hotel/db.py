"""Connection handling, schema bootstrap and the transaction helper."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DEFAULT_DB = ROOT / "data" / "hotel.db"


class HotelError(Exception):
    """Any business-rule or validation failure that should be shown to the user."""


def connect(path=DEFAULT_DB, read_only=False):
    """Open a connection.

    isolation_level=None puts the driver in autocommit mode, so *we* decide
    exactly where a transaction begins and ends (see `transaction`).
    """
    path = str(path)
    if path == ":memory:":
        conn = sqlite3.connect(path, isolation_level=None)
    elif read_only:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite leaves FK checks off by default
    return conn


def init_db(conn):
    """Create tables, triggers and views (idempotent)."""
    for name in ("schema.sql", "triggers.sql", "views.sql"):
        conn.executescript((SQL_DIR / name).read_text(encoding="utf-8"))


@contextmanager
def transaction(conn):
    """ACID block: everything inside commits together or not at all.

    BEGIN IMMEDIATE takes the write lock up front, so two terminals cannot
    both pass the availability check and then both insert.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
