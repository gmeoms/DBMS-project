"""Staff accounts with salted PBKDF2 password hashes."""
import hashlib
import hmac
import os
import sqlite3

from .db import HotelError

ITERATIONS = 120_000


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()


def create_user(conn, username, password, role="RECEPTIONIST"):
    if len(username.strip()) < 3:
        raise HotelError("Username must be at least 3 characters")
    if len(password) < 6:
        raise HotelError("Password must be at least 6 characters")
    salt = os.urandom(16)
    try:
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, salt, role) VALUES (?,?,?,?)",
            (username.strip(), _hash(password, salt), salt.hex(), role.upper()),
        )
    except sqlite3.IntegrityError as exc:
        raise HotelError("Username already taken or invalid role") from exc
    return cur.lastrowid


def authenticate(conn, username, password):
    """Return the user row on success, otherwise None."""
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    if user is None:
        return None
    expected = _hash(password, bytes.fromhex(user["salt"]))
    return user if hmac.compare_digest(expected, user["password_hash"]) else None
