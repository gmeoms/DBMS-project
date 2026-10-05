"""Booking life-cycle: create, pay, check in/out, cancel.

Rules that must *always* hold (no overlap, valid status flow, payment limits)
live in sql/triggers.sql. This module adds the rules that need calculation
or today's date: pricing, refund policy, date windows.
"""
import sqlite3
from datetime import date, timedelta

from .db import HotelError, transaction
from .utils import parse_date

WEEKEND_SURCHARGE = 1.20      # Friday and Saturday nights
LONG_STAY_DISCOUNT = 0.90     # 7+ nights
MAX_NIGHTS = 30


def calculate_price(base_price, check_in, check_out):
    total, night = 0.0, check_in
    while night < check_out:
        total += base_price * (WEEKEND_SURCHARGE if night.weekday() in (4, 5) else 1.0)
        night += timedelta(days=1)
    if (check_out - check_in).days >= 7:
        total *= LONG_STAY_DISCOUNT
    return round(total, 2)


def refund_percent(check_in, today):
    days_left = (check_in - today).days
    if days_left >= 7:
        return 100
    if days_left >= 1:
        return 50
    return 0


def get_booking(conn, booking_id):
    row = conn.execute("SELECT * FROM v_booking_details WHERE booking_id = ?", (booking_id,)).fetchone()
    if row is None:
        raise HotelError(f"Booking #{booking_id} not found")
    return row


def create_booking(conn, guest_id, room_number, check_in, check_out, staff_id=None, today=None):
    ci, co = parse_date(check_in), parse_date(check_out)
    today = today or date.today()
    if co <= ci:
        raise HotelError("Check-out must be after check-in")
    if ci < today:
        raise HotelError("Check-in date cannot be in the past")
    if (co - ci).days > MAX_NIGHTS:
        raise HotelError(f"Maximum stay is {MAX_NIGHTS} nights")

    with transaction(conn):
        room = conn.execute(
            """SELECT r.room_id, rt.base_price FROM rooms r
               JOIN room_types rt ON rt.type_id = r.type_id WHERE r.room_number = ?""",
            (room_number.strip(),),
        ).fetchone()
        if room is None:
            raise HotelError(f"Room {room_number} not found")
        if conn.execute("SELECT 1 FROM guests WHERE guest_id = ?", (guest_id,)).fetchone() is None:
            raise HotelError("Guest not found")
        total = calculate_price(room["base_price"], ci, co)
        try:
            cur = conn.execute(
                """INSERT INTO bookings(guest_id, room_id, check_in, check_out, total_amount, created_by)
                   VALUES (?,?,?,?,?,?)""",
                (guest_id, room["room_id"], ci.isoformat(), co.isoformat(), total, staff_id),
            )
        except sqlite3.IntegrityError as exc:
            raise HotelError(str(exc)) from exc   # message comes from the trigger
        return cur.lastrowid


def record_payment(conn, booking_id, amount, method):
    get_booking(conn, booking_id)
    try:
        conn.execute(
            "INSERT INTO payments(booking_id, kind, amount, method) VALUES (?, 'PAYMENT', ?, ?)",
            (booking_id, round(amount, 2), method.upper()),
        )
    except sqlite3.IntegrityError as exc:
        raise HotelError(str(exc)) from exc


def _set_status(conn, booking_id, new_status):
    current = conn.execute("SELECT status FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    if current and current["status"] == new_status:   # trigger only guards real changes
        raise HotelError(f"Booking #{booking_id} is already {new_status}")
    try:
        conn.execute("UPDATE bookings SET status = ? WHERE booking_id = ?", (new_status, booking_id))
    except sqlite3.IntegrityError as exc:
        raise HotelError(str(exc)) from exc


def check_in_guest(conn, booking_id, today=None):
    today = today or date.today()
    with transaction(conn):
        b = get_booking(conn, booking_id)
        if not (parse_date(b["check_in"]) <= today < parse_date(b["check_out"])):
            raise HotelError(f"Check-in is only allowed between {b['check_in']} and {b['check_out']}")
        _set_status(conn, booking_id, "CHECKED_IN")


def check_out_guest(conn, booking_id):
    with transaction(conn):
        b = get_booking(conn, booking_id)
        balance = round(b["total_amount"] - b["net_paid"], 2)
        if b["status"] == "CHECKED_IN" and balance > 0:
            raise HotelError(f"Outstanding balance of Rs {balance:,.2f} must be paid before check-out")
        _set_status(conn, booking_id, "CHECKED_OUT")


def cancel_booking(conn, booking_id, today=None):
    """Cancel + refund atomically. Returns (refund_amount, percent)."""
    today = today or date.today()
    with transaction(conn):
        b = get_booking(conn, booking_id)
        _set_status(conn, booking_id, "CANCELLED")
        pct = refund_percent(parse_date(b["check_in"]), today)
        refund = round(b["net_paid"] * pct / 100, 2)
        if refund > 0:
            last = conn.execute(
                "SELECT method FROM payments WHERE booking_id = ? AND kind = 'PAYMENT' "
                "ORDER BY payment_id DESC LIMIT 1", (booking_id,)).fetchone()
            conn.execute(
                "INSERT INTO payments(booking_id, kind, amount, method) VALUES (?, 'REFUND', ?, ?)",
                (booking_id, refund, last["method"]),
            )
        return refund, pct


def list_bookings(conn, status=None, term=None):
    sql, args = "SELECT * FROM v_booking_details WHERE 1=1", []
    if status:
        sql += " AND status = ?"
        args.append(status.upper())
    if term:
        sql += " AND (guest LIKE ? OR email LIKE ? OR room_number = ?)"
        args += [f"%{term}%", f"%{term}%", term]
    return conn.execute(sql + " ORDER BY check_in, booking_id", args).fetchall()
