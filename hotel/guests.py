"""Guest records."""
import sqlite3

from .db import HotelError


def add_guest(conn, full_name, email, phone=None):
    try:
        cur = conn.execute(
            "INSERT INTO guests(full_name, email, phone) VALUES (?,?,?)",
            (full_name.strip(), email.strip(), (phone or "").strip() or None),
        )
    except sqlite3.IntegrityError as exc:
        raise HotelError("Could not add guest: duplicate or invalid name/email/phone") from exc
    return cur.lastrowid


def search_guests(conn, term):
    like = f"%{term.strip()}%"
    return conn.execute(
        "SELECT guest_id, full_name, email, phone FROM guests "
        "WHERE full_name LIKE ? OR email LIKE ? ORDER BY full_name",
        (like, like),
    ).fetchall()


def get_by_email(conn, email):
    return conn.execute("SELECT * FROM guests WHERE email = ?", (email.strip(),)).fetchone()
