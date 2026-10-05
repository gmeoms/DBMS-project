"""Analytics (joins, aggregates, window functions), calendar and invoices."""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .bookings import get_booking
from .db import HotelError, ROOT
from .utils import money, parse_date

COUNTED = "('CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT')"


def summary(conn):
    return {
        "bookings_by_status": conn.execute(
            "SELECT status, COUNT(*) AS count FROM bookings GROUP BY status ORDER BY status").fetchall(),
        "revenue_by_type": conn.execute(
            "SELECT * FROM v_revenue_by_room_type ORDER BY net_revenue DESC").fetchall(),
        "monthly": conn.execute(
            """SELECT strftime('%Y-%m', paid_at) AS month,
                      SUM(CASE kind WHEN 'PAYMENT' THEN amount ELSE 0 END) AS collected,
                      SUM(CASE kind WHEN 'REFUND'  THEN amount ELSE 0 END) AS refunded,
                      SUM(CASE kind WHEN 'PAYMENT' THEN amount ELSE -amount END) AS net
               FROM payments GROUP BY month ORDER BY month""").fetchall(),
        "outstanding": conn.execute(
            "SELECT * FROM v_outstanding_balances ORDER BY balance_due DESC").fetchall(),
    }


def occupancy(conn, start, end):
    """Occupancy per room type for the half-open period [start, end)."""
    s, e = parse_date(start), parse_date(end)
    if e <= s:
        raise HotelError("End date must be after start date")
    days = (e - s).days
    rows = conn.execute(
        f"""SELECT rt.name AS room_type,
                   COUNT(DISTINCT r.room_id) AS rooms,
                   COALESCE(SUM(MAX(0, julianday(MIN(b.check_out, :e)) -
                                       julianday(MAX(b.check_in,  :s)))), 0) AS booked_nights
            FROM room_types rt
            JOIN rooms r ON r.type_id = rt.type_id
            LEFT JOIN bookings b ON b.room_id = r.room_id AND b.status IN {COUNTED}
            GROUP BY rt.type_id ORDER BY rt.name""",
        {"s": s.isoformat(), "e": e.isoformat()},
    ).fetchall()
    result = []
    for r in rows:
        capacity = r["rooms"] * days
        result.append({
            "room_type": r["room_type"], "rooms": r["rooms"],
            "booked_nights": int(r["booked_nights"]), "available_nights": capacity,
            "occupancy_%": round(100 * r["booked_nights"] / capacity, 1) if capacity else 0.0,
        })
    return result


def top_guests(conn, limit=5):
    """Window function: RANK() over total spend."""
    return conn.execute(
        """SELECT RANK() OVER (ORDER BY SUM(net_paid) DESC) AS rank,
                  guest, COUNT(*) AS bookings, SUM(net_paid) AS total_spent
           FROM v_booking_details GROUP BY email
           ORDER BY rank, guest LIMIT ?""", (limit,)).fetchall()


def audit_trail(conn, limit=20):
    return conn.execute(
        "SELECT log_id, logged_at, table_name, record_id, action, details "
        "FROM audit_log ORDER BY log_id DESC LIMIT ?", (limit,)).fetchall()


def availability_calendar(conn, start, days=14):
    """ASCII grid: '.' free  '#' booked  '@' guest in house  'M' maintenance."""
    s = parse_date(start)
    e = s + timedelta(days=days)
    rooms = conn.execute("SELECT room_id, room_number, status FROM rooms ORDER BY room_number").fetchall()
    busy = defaultdict(dict)
    for b in conn.execute(
        f"""SELECT room_id, check_in, check_out, status FROM bookings
            WHERE status IN {COUNTED} AND check_in < ? AND check_out > ?""",
        (e.isoformat(), s.isoformat()),
    ):
        d, end = parse_date(b["check_in"]), parse_date(b["check_out"])
        while d < end:
            busy[b["room_id"]][d] = "@" if b["status"] == "CHECKED_IN" else "#"
            d += timedelta(days=1)
    day_list = [s + timedelta(days=i) for i in range(days)]
    lines = ["Room  " + " ".join(f"{d.day:02d}" for d in day_list),
             "      " + " ".join(d.strftime("%a")[:2] for d in day_list)]
    for r in rooms:
        default = "M" if r["status"] == "MAINTENANCE" else "."
        cells = [busy[r["room_id"]].get(d, default) for d in day_list]
        lines.append(f"{r['room_number']:<5} " + " ".join(f" {c}" for c in cells))
    lines.append("Legend: . free   # booked   @ in house   M maintenance")
    return "\n".join(lines)


def invoice_text(conn, booking_id):
    b = get_booking(conn, booking_id)
    pays = conn.execute(
        "SELECT kind, amount, method, paid_at FROM payments WHERE booking_id = ? ORDER BY payment_id",
        (booking_id,)).fetchall()
    bar = "=" * 57
    lines = [bar, "                 HOTEL BOOKING INVOICE", bar,
             f" Invoice / Booking : INV{booking_id:05d}",
             f" Guest             : {b['guest']} ({b['email']})",
             f" Room              : {b['room_number']} ({b['room_type']})",
             f" Stay              : {b['check_in']} -> {b['check_out']} ({b['nights']} nights)",
             f" Status            : {b['status']}", "-" * 57,
             f" Total charges     : {money(b['total_amount'])}"]
    for p in pays:
        sign = "-" if p["kind"] == "REFUND" else " "
        lines.append(f"  {p['paid_at']}  {p['kind']:<7} {sign}{money(p['amount'])}  ({p['method']})")
    lines += ["-" * 57, f" Net paid          : {money(b['net_paid'])}",
              f" Balance due       : {money(b['total_amount'] - b['net_paid'])}", bar]
    return "\n".join(lines)


def export_invoice(conn, booking_id, folder=None):
    folder = Path(folder or ROOT / "invoices")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"INV{booking_id:05d}.txt"
    path.write_text(invoice_text(conn, booking_id), encoding="utf-8")
    return path
