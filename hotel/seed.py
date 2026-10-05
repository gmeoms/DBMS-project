"""Demo data: reference rows from seed.sql plus staff and a few realistic bookings."""
from datetime import date, timedelta

from . import auth, bookings
from .db import SQL_DIR, init_db


def seed_if_empty(conn):
    init_db(conn)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return False
    conn.executescript((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
    admin = auth.create_user(conn, "admin", "admin123", "ADMIN")
    auth.create_user(conn, "desk", "desk123", "RECEPTIONIST")

    today = date.today()
    day = lambda n: (today + timedelta(days=n)).isoformat()
    gid = lambda email: conn.execute("SELECT guest_id FROM guests WHERE email=?", (email,)).fetchone()[0]

    # completed stay (backdated by passing `today`)
    b = bookings.create_booking(conn, gid("meera@example.com"), "102", day(-6), day(-3), admin, today=today - timedelta(days=6))
    bookings.record_payment(conn, b, bookings.get_booking(conn, b)["total_amount"], "CARD")
    bookings.check_in_guest(conn, b, today=today - timedelta(days=6))
    bookings.check_out_guest(conn, b)
    # guest currently in house
    b = bookings.create_booking(conn, gid("vikram@example.com"), "301", day(-1), day(3), admin, today=today - timedelta(days=1))
    bookings.record_payment(conn, b, 10000, "UPI")
    bookings.check_in_guest(conn, b, today=today - timedelta(days=1))
    # upcoming bookings
    b = bookings.create_booking(conn, gid("rajat@example.com"), "201", day(3), day(6), admin)
    bookings.record_payment(conn, b, 4000, "CASH")
    b = bookings.create_booking(conn, gid("ananya@example.com"), "103", day(10), day(12), admin)
    bookings.record_payment(conn, b, 2000, "UPI")
    return True
