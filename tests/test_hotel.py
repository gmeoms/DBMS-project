"""Run with:  python -m unittest discover -v"""
import sqlite3
import unittest
from datetime import date, timedelta

from hotel import auth, bookings, db, guests, reports, rooms, seed
from hotel.db import HotelError

TODAY = date.today()


def d(n):
    return (TODAY + timedelta(days=n)).isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.init_db(self.conn)
        self.conn.executescript((db.SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
        self.gid = guests.get_by_email(self.conn, "rajat@example.com")["guest_id"]
        self.gid2 = guests.get_by_email(self.conn, "ananya@example.com")["guest_id"]

    def book(self, room="101", a=10, b=13, gid=None):
        return bookings.create_booking(self.conn, gid or self.gid, room, d(a), d(b))


class TestSchemaConstraints(Base):
    def test_foreign_keys_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO rooms(room_number, floor, type_id) VALUES ('999', 1, 999)")

    def test_check_constraint_dates(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO bookings(guest_id, room_id, check_in, check_out, total_amount)"
                              " VALUES (1, 1, '2030-01-05', '2030-01-05', 100)")

    def test_unique_email(self):
        with self.assertRaises(HotelError):
            guests.add_guest(self.conn, "Dup", "RAJAT@example.com")

    def test_bad_email_rejected(self):
        with self.assertRaises(HotelError):
            guests.add_guest(self.conn, "X", "not-an-email")

    def test_cannot_delete_room_with_bookings(self):
        self.book()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM rooms WHERE room_number = '101'")


class TestBookingRules(Base):
    def test_overlap_rejected(self):
        self.book("101", 10, 13)
        with self.assertRaises(HotelError) as ctx:
            self.book("101", 12, 15, self.gid2)
        self.assertIn("already booked", str(ctx.exception))

    def test_back_to_back_allowed(self):
        self.book("101", 10, 13)
        self.book("101", 13, 15, self.gid2)   # check-in on the other guest's check-out day

    def test_trigger_blocks_raw_sql_too(self):
        self.book("101", 10, 13)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO bookings(guest_id, room_id, check_in, check_out, total_amount)"
                              " VALUES (1, 1, ?, ?, 100)", (d(11), d(12)))

    def test_cancelled_booking_frees_room(self):
        bid = self.book("101", 10, 13)
        bookings.cancel_booking(self.conn, bid)
        self.book("101", 10, 13, self.gid2)

    def test_maintenance_room_blocked(self):
        rooms.set_room_status(self.conn, "101", "MAINTENANCE")
        with self.assertRaises(HotelError):
            self.book("101")

    def test_cannot_maintain_room_with_future_booking(self):
        self.book("101")
        with self.assertRaises(HotelError):
            rooms.set_room_status(self.conn, "101", "MAINTENANCE")

    def test_past_and_long_stays_rejected(self):
        with self.assertRaises(HotelError):
            bookings.create_booking(self.conn, self.gid, "101", d(-2), d(1))
        with self.assertRaises(HotelError):
            self.book("101", 5, 50)

    def test_failed_transaction_rolls_back(self):
        before = self.conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        with self.assertRaises(HotelError):
            bookings.create_booking(self.conn, 9999, "101", d(5), d(6))  # unknown guest
        self.assertEqual(before, self.conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0])
        self.assertFalse(self.conn.in_transaction)


class TestPricing(unittest.TestCase):
    def monday(self):
        x = date(2030, 1, 7)
        self.assertEqual(x.weekday(), 0)
        return x

    def test_weekday_price(self):
        m = self.monday()
        self.assertEqual(bookings.calculate_price(1000, m, m + timedelta(days=2)), 2000)

    def test_weekend_surcharge(self):
        fri = self.monday() + timedelta(days=4)
        self.assertEqual(bookings.calculate_price(1000, fri, fri + timedelta(days=2)), 2400)

    def test_long_stay_discount(self):
        m = self.monday()
        # 7 nights: Fri + Sat surcharged -> 7000 + 400 = 7400, minus 10%
        self.assertEqual(bookings.calculate_price(1000, m, m + timedelta(days=7)), 6660)

    def test_refund_policy(self):
        t = date(2030, 1, 1)
        self.assertEqual(bookings.refund_percent(t + timedelta(days=10), t), 100)
        self.assertEqual(bookings.refund_percent(t + timedelta(days=3), t), 50)
        self.assertEqual(bookings.refund_percent(t, t), 0)


class TestPaymentsAndLifecycle(Base):
    def test_overpayment_blocked(self):
        bid = self.book()
        total = bookings.get_booking(self.conn, bid)["total_amount"]
        with self.assertRaises(HotelError):
            bookings.record_payment(self.conn, bid, total + 1, "CASH")

    def test_cancel_refunds_by_policy(self):
        bid = self.book("101", 20, 22)
        bookings.record_payment(self.conn, bid, 1000, "UPI")
        refund, pct = bookings.cancel_booking(self.conn, bid)
        self.assertEqual((refund, pct), (1000, 100))
        self.assertEqual(bookings.get_booking(self.conn, bid)["net_paid"], 0)

    def test_late_cancel_half_refund(self):
        bid = self.book("101", 3, 5)
        bookings.record_payment(self.conn, bid, 1000, "CASH")
        refund, pct = bookings.cancel_booking(self.conn, bid)
        self.assertEqual((refund, pct), (500, 50))

    def test_no_payment_on_cancelled(self):
        bid = self.book()
        bookings.cancel_booking(self.conn, bid)
        with self.assertRaises(HotelError):
            bookings.record_payment(self.conn, bid, 100, "CASH")

    def test_status_machine(self):
        bid = self.book()
        with self.assertRaises(HotelError):           # CONFIRMED -> CHECKED_OUT not allowed
            bookings.check_out_guest(self.conn, bid)
        bookings.cancel_booking(self.conn, bid)
        with self.assertRaises(HotelError):           # CANCELLED is final
            bookings.cancel_booking(self.conn, bid)

    def test_full_stay_needs_full_payment(self):
        bid = bookings.create_booking(self.conn, self.gid, "102", d(0), d(2))
        bookings.check_in_guest(self.conn, bid)
        with self.assertRaises(HotelError):
            bookings.check_out_guest(self.conn, bid)
        bookings.record_payment(self.conn, bid, bookings.get_booking(self.conn, bid)["total_amount"], "CARD")
        bookings.check_out_guest(self.conn, bid)
        self.assertEqual(bookings.get_booking(self.conn, bid)["status"], "CHECKED_OUT")

    def test_checkin_window(self):
        bid = self.book("101", 10, 12)
        with self.assertRaises(HotelError):
            bookings.check_in_guest(self.conn, bid)   # too early


class TestQueriesAndReports(Base):
    def test_availability_search(self):
        self.book("101", 10, 13)
        numbers = [r["room_number"] for r in rooms.find_available(self.conn, d(11), d(12))]
        self.assertNotIn("101", numbers)
        self.assertIn("102", numbers)
        suites = rooms.find_available(self.conn, d(11), d(12), min_capacity=4)
        self.assertEqual({r["room_type"] for r in suites}, {"Suite"})

    def test_audit_trigger_logs_everything(self):
        bid = self.book()
        bookings.record_payment(self.conn, bid, 500, "CASH")
        bookings.cancel_booking(self.conn, bid)
        actions = [r["action"] for r in reports.audit_trail(self.conn, 50)]
        for expected in ("CREATED", "PAYMENT", "STATUS_CHANGE", "REFUND"):
            self.assertIn(expected, actions)

    def test_occupancy_math(self):
        self.book("101", 0 + 1, 4)        # 3 nights inside window
        rows = {r["room_type"]: r for r in reports.occupancy(self.conn, d(0), d(10))}
        self.assertEqual(rows["Standard"]["booked_nights"], 3)
        self.assertEqual(rows["Standard"]["available_nights"], 4 * 10)
        self.assertEqual(rows["Standard"]["occupancy_%"], 7.5)

    def test_occupancy_clips_partial_overlap(self):
        self.book("101", 8, 14)           # window ends day 10 -> only 2 nights count
        row = next(r for r in reports.occupancy(self.conn, d(0), d(10)) if r["room_type"] == "Standard")
        self.assertEqual(row["booked_nights"], 2)

    def test_top_guests_rank(self):
        a = self.book("101", 10, 12)
        b = self.book("102", 10, 12, self.gid2)
        bookings.record_payment(self.conn, a, 3000, "CASH")
        bookings.record_payment(self.conn, b, 1000, "CASH")
        top = reports.top_guests(self.conn)
        self.assertEqual((top[0]["rank"], top[0]["guest"]), (1, "Rajat Kumar"))

    def test_invoice_export(self):
        import tempfile
        bid = self.book()
        path = reports.export_invoice(self.conn, bid, tempfile.mkdtemp())
        self.assertIn("HOTEL BOOKING INVOICE", path.read_text(encoding="utf-8"))

    def test_availability_query_uses_index(self):
        plan = " ".join(r["detail"] for r in self.conn.execute(
            "EXPLAIN QUERY PLAN SELECT 1 FROM bookings WHERE room_id = 1 AND check_in < '2030-01-01' "
            "AND check_out > '2029-01-01'"))
        self.assertIn("idx_bookings_room_dates", plan)


class TestAuthAndSeed(unittest.TestCase):
    def test_auth(self):
        conn = db.connect(":memory:")
        db.init_db(conn)
        auth.create_user(conn, "alice", "secret1", "admin")
        self.assertIsNotNone(auth.authenticate(conn, "ALICE", "secret1"))
        self.assertIsNone(auth.authenticate(conn, "alice", "wrong"))
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotIn("secret1", stored)
        with self.assertRaises(HotelError):
            auth.create_user(conn, "alice", "another1")

    def test_seed_is_idempotent(self):
        conn = db.connect(":memory:")
        self.assertTrue(seed.seed_if_empty(conn))
        self.assertFalse(seed.seed_if_empty(conn))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0], 10)


if __name__ == "__main__":
    unittest.main()
