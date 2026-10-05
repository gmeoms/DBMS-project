"""Terminal menu. Contains no SQL business logic - it only calls the service modules."""
import getpass
import sqlite3
from datetime import date, timedelta

from . import auth, bookings, guests, reports, rooms
from .db import HotelError, connect
from .utils import format_table, money

LINE = "=" * 62


# ---------------------------------------------------------------- input helpers
def ask(label, default=None, cast=str):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {label}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        if not raw:
            print("    A value is required.")
            continue
        try:
            return cast(raw)
        except ValueError:
            print("    Invalid input, try again.")


def show(rows, headers=None):
    print(format_table(rows, headers))


def title(text):
    print(f"\n{LINE}\n  {text}\n{LINE}")


# ---------------------------------------------------------------- receptionist actions
def a_search_rooms(conn, user):
    title("SEARCH AVAILABLE ROOMS")
    ci = ask("Check-in  (YYYY-MM-DD)")
    co = ask("Check-out (YYYY-MM-DD)")
    cap = ask("Guests", 1, int)
    show(rooms.find_available(conn, ci, co, cap),
         ["room_number", "floor", "room_type", "capacity", "base_price", "amenities"])


def a_add_guest(conn, user):
    title("REGISTER GUEST")
    gid = guests.add_guest(conn, ask("Full name"), ask("Email"), input("  Phone (optional): "))
    print(f"  Guest registered with id {gid}.")


def a_find_guest(conn, user):
    title("FIND GUEST")
    show(guests.search_guests(conn, ask("Name or email contains")))


def a_new_booking(conn, user):
    title("NEW BOOKING")
    guest = guests.get_by_email(conn, ask("Guest email"))
    if guest is None:
        raise HotelError("No guest with that email - register the guest first")
    ci, co = ask("Check-in  (YYYY-MM-DD)"), ask("Check-out (YYYY-MM-DD)")
    free = rooms.find_available(conn, ci, co, ask("Guests", 1, int))
    show(free, ["room_number", "room_type", "base_price", "amenities"])
    if not free:
        return
    number = ask("Room number to book")
    bid = bookings.create_booking(conn, guest["guest_id"], number, ci, co, user["user_id"])
    b = bookings.get_booking(conn, bid)
    print(f"\n  Booking #{bid} confirmed: room {number}, {b['nights']} nights, total {money(b['total_amount'])}")
    if input("  Take a deposit now? (y/N): ").lower() == "y":
        bookings.record_payment(conn, bid, ask("Amount", cast=float), ask("Method (CASH/CARD/UPI)", "CASH"))
        print("  Payment recorded.")


def a_payment(conn, user):
    title("RECORD PAYMENT")
    bid = ask("Booking id", cast=int)
    bookings.record_payment(conn, bid, ask("Amount", cast=float), ask("Method (CASH/CARD/UPI)", "CASH"))
    print("  Payment recorded.")


def a_check_in(conn, user):
    bookings.check_in_guest(conn, ask("Booking id", cast=int))
    print("  Guest checked in.")


def a_check_out(conn, user):
    bookings.check_out_guest(conn, ask("Booking id", cast=int))
    print("  Guest checked out.")


def a_cancel(conn, user):
    title("CANCEL BOOKING")
    refund, pct = bookings.cancel_booking(conn, ask("Booking id", cast=int))
    print(f"  Cancelled. Refund policy {pct}% -> refunded {money(refund)}.")


def a_list_bookings(conn, user):
    title("BOOKINGS")
    status = input("  Filter by status (blank = all): ").strip() or None
    term = input("  Guest name / email / room (blank = all): ").strip() or None
    show(bookings.list_bookings(conn, status, term),
         ["booking_id", "guest", "room_number", "check_in", "check_out", "status", "total_amount", "net_paid"])


def a_calendar(conn, user):
    title("AVAILABILITY CALENDAR")
    start = ask("Start date", date.today().isoformat())
    print(reports.availability_calendar(conn, start, 14))


def a_invoice(conn, user):
    bid = ask("Booking id", cast=int)
    print(reports.invoice_text(conn, bid))
    print(f"\n  Saved to {reports.export_invoice(conn, bid)}")


# ---------------------------------------------------------------- admin actions
def a_add_room_type(conn, user):
    rooms.add_room_type(conn, ask("Name"), ask("Base price", cast=float), ask("Capacity", cast=int))
    print("  Room type added.")


def a_add_room(conn, user):
    rooms.add_room(conn, ask("Room number"), ask("Floor", cast=int), ask("Room type"))
    print("  Room added.")


def a_room_status(conn, user):
    show(rooms.list_rooms(conn), ["room_number", "room_type", "status"])
    rooms.set_room_status(conn, ask("Room number"), ask("New status (AVAILABLE/MAINTENANCE)"))
    print("  Status updated.")


def a_amenity(conn, user):
    rooms.add_amenity_to_room(conn, ask("Room number"), ask("Amenity"))
    print("  Amenity linked.")


def a_reports(conn, user):
    title("MANAGEMENT REPORT")
    s = reports.summary(conn)
    print("\n  Bookings by status");     show(s["bookings_by_status"])
    print("\n  Net revenue by room type"); show(s["revenue_by_type"])
    print("\n  Monthly cash flow");      show(s["monthly"])
    print("\n  Outstanding balances");   show(s["outstanding"])
    print("\n  Top guests (RANK window function)"); show(reports.top_guests(conn))
    today = date.today()
    print(f"\n  Occupancy, next 30 days")
    show(reports.occupancy(conn, today, today + timedelta(days=30)))


def a_audit(conn, user):
    title("AUDIT LOG (latest 20)")
    show(reports.audit_trail(conn))


def a_new_user(conn, user):
    auth.create_user(conn, ask("Username"), getpass.getpass("  Password: "), ask("Role (ADMIN/RECEPTIONIST)", "RECEPTIONIST"))
    print("  User created.")


def a_sql_console(conn, user):
    """Read-only SQL shell: opens a *second* connection with mode=ro."""
    title("READ-ONLY SQL CONSOLE")
    print("  Type a SELECT query. Commands: .tables  .schema <table>  explain <query>  exit")
    ro = connect(conn.execute("PRAGMA database_list").fetchone()["file"], read_only=True)
    while True:
        q = input("  sql> ").strip().rstrip(";")
        if q.lower() in ("exit", "quit", ""):
            return
        if q == ".tables":
            q = "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        elif q.startswith(".schema"):
            name = q.split(maxsplit=1)[1] if " " in q else ""
            q = f"SELECT sql FROM sqlite_master WHERE name = '{name.replace(chr(39), '')}'"
        elif q.lower().startswith("explain "):
            q = "EXPLAIN QUERY PLAN " + q[8:]
        try:
            rows = ro.execute(q).fetchmany(50)
            show(rows, [d[0] for d in ro.execute(q).description] if rows else None)
        except sqlite3.Error as exc:
            print(f"  SQL error: {exc}")


# ---------------------------------------------------------------- menus
STAFF_MENU = [
    ("Search available rooms", a_search_rooms), ("Register guest", a_add_guest),
    ("Find guest", a_find_guest), ("New booking", a_new_booking),
    ("Record payment", a_payment), ("Check-in guest", a_check_in),
    ("Check-out guest", a_check_out), ("Cancel booking (with refund)", a_cancel),
    ("View bookings", a_list_bookings), ("Availability calendar", a_calendar),
    ("Print / export invoice", a_invoice),
]
ADMIN_MENU = [
    ("Add room type", a_add_room_type), ("Add room", a_add_room),
    ("Set room status", a_room_status), ("Add amenity to room", a_amenity),
    ("Management reports", a_reports), ("Audit log", a_audit),
    ("Create staff user", a_new_user), ("Read-only SQL console", a_sql_console),
]


def login(conn):
    print(f"{LINE}\n   HOTEL RESERVATION SYSTEM  -  staff login\n{LINE}")
    for _ in range(3):
        user = auth.authenticate(conn, input("  Username: "), getpass.getpass("  Password: "))
        if user:
            return user
        print("  Invalid credentials.")
    return None


def run(conn):
    user = login(conn)
    if user is None:
        print("  Too many failed attempts.")
        return
    menu = STAFF_MENU + (ADMIN_MENU if user["role"] == "ADMIN" else [])
    print(f"\n  Welcome, {user['username']} ({user['role']})")
    while True:
        print(f"\n{LINE}\n  MAIN MENU\n{LINE}")
        for i, (label, _) in enumerate(menu, 1):
            print(f"  {i:>2}. {label}")
        print("   0. Exit")
        try:
            choice = input("\n  Choose: ").strip()
            if choice == "0":
                print("  Goodbye.")
                return
            if not (choice.isdigit() and 1 <= int(choice) <= len(menu)):
                print("  Invalid choice.")
                continue
            menu[int(choice) - 1][1](conn, user)
        except HotelError as exc:
            print(f"\n  [!] {exc}")
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
