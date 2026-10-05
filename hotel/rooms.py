"""Room types, rooms, amenities and the availability search."""
import sqlite3

from .db import HotelError, transaction
from .utils import parse_date

_ROOM_COLUMNS = """
    r.room_number, r.floor, rt.name AS room_type, rt.capacity, rt.base_price,
    r.status, COALESCE(GROUP_CONCAT(a.name, ', '), '') AS amenities
"""
_ROOM_JOINS = """
    FROM rooms r
    JOIN room_types rt        ON rt.type_id = r.type_id
    LEFT JOIN room_amenities ra ON ra.room_id = r.room_id
    LEFT JOIN amenities a       ON a.amenity_id = ra.amenity_id
"""


def add_room_type(conn, name, base_price, capacity):
    try:
        cur = conn.execute(
            "INSERT INTO room_types(name, base_price, capacity) VALUES (?,?,?)",
            (name.strip(), base_price, capacity),
        )
    except sqlite3.IntegrityError as exc:
        raise HotelError("Invalid room type (duplicate name, price <= 0 or bad capacity)") from exc
    return cur.lastrowid


def add_room(conn, room_number, floor, type_name):
    row = conn.execute("SELECT type_id FROM room_types WHERE name = ?", (type_name.strip(),)).fetchone()
    if row is None:
        raise HotelError(f"Unknown room type '{type_name}'")
    try:
        cur = conn.execute(
            "INSERT INTO rooms(room_number, floor, type_id) VALUES (?,?,?)",
            (room_number.strip(), floor, row["type_id"]),
        )
    except sqlite3.IntegrityError as exc:
        raise HotelError("Could not add room (duplicate number or invalid floor)") from exc
    return cur.lastrowid


def list_rooms(conn):
    return conn.execute(
        f"SELECT {_ROOM_COLUMNS} {_ROOM_JOINS} GROUP BY r.room_id ORDER BY r.room_number"
    ).fetchall()


def find_available(conn, check_in, check_out, min_capacity=1, room_type=None):
    """Rooms that are usable and have no overlapping active booking."""
    ci, co = parse_date(check_in), parse_date(check_out)
    if co <= ci:
        raise HotelError("Check-out must be after check-in")
    return conn.execute(
        f"""SELECT {_ROOM_COLUMNS} {_ROOM_JOINS}
            WHERE r.status = 'AVAILABLE'
              AND rt.capacity >= :cap
              AND (:rtype IS NULL OR rt.name = :rtype COLLATE NOCASE)
              AND NOT EXISTS (
                    SELECT 1 FROM bookings b
                    WHERE b.room_id = r.room_id
                      AND b.status IN ('CONFIRMED', 'CHECKED_IN')
                      AND :ci < b.check_out AND :co > b.check_in)
            GROUP BY r.room_id
            ORDER BY rt.base_price, r.room_number""",
        {"cap": min_capacity, "rtype": room_type, "ci": ci.isoformat(), "co": co.isoformat()},
    ).fetchall()


def set_room_status(conn, room_number, status):
    try:
        cur = conn.execute(
            "UPDATE rooms SET status = ? WHERE room_number = ?", (status.upper(), room_number.strip())
        )
    except sqlite3.IntegrityError as exc:  # raised by CHECK or by the maintenance trigger
        raise HotelError(str(exc)) from exc
    if cur.rowcount == 0:
        raise HotelError(f"Room {room_number} not found")


def add_amenity_to_room(conn, room_number, amenity):
    with transaction(conn):
        room = conn.execute("SELECT room_id FROM rooms WHERE room_number = ?", (room_number.strip(),)).fetchone()
        if room is None:
            raise HotelError(f"Room {room_number} not found")
        conn.execute("INSERT OR IGNORE INTO amenities(name) VALUES (?)", (amenity.strip(),))
        conn.execute(
            """INSERT OR IGNORE INTO room_amenities(room_id, amenity_id)
               SELECT ?, amenity_id FROM amenities WHERE name = ?""",
            (room["room_id"], amenity.strip()),
        )
