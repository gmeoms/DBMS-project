-- =====================================================================
-- triggers.sql : business rules enforced INSIDE the database
-- Even a direct INSERT from a SQL shell cannot break these rules.
-- =====================================================================

-- 1. No double booking: reject overlapping active bookings for a room.
--    Two stays overlap when  new.in < old.out  AND  new.out > old.in
--    (so a guest may check in on the day another checks out).
CREATE TRIGGER IF NOT EXISTS trg_booking_no_overlap_ins
BEFORE INSERT ON bookings
WHEN NEW.status IN ('CONFIRMED', 'CHECKED_IN')
BEGIN
    SELECT RAISE(ABORT, 'Room is already booked for the selected dates')
    WHERE EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.room_id = NEW.room_id
          AND b.status IN ('CONFIRMED', 'CHECKED_IN')
          AND NEW.check_in < b.check_out
          AND NEW.check_out > b.check_in
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_booking_no_overlap_upd
BEFORE UPDATE OF room_id, check_in, check_out, status ON bookings
WHEN NEW.status IN ('CONFIRMED', 'CHECKED_IN')
BEGIN
    SELECT RAISE(ABORT, 'Room is already booked for the selected dates')
    WHERE EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.room_id = NEW.room_id
          AND b.booking_id <> NEW.booking_id
          AND b.status IN ('CONFIRMED', 'CHECKED_IN')
          AND NEW.check_in < b.check_out
          AND NEW.check_out > b.check_in
    );
END;

-- 2. Rooms under maintenance cannot be booked.
CREATE TRIGGER IF NOT EXISTS trg_booking_room_usable
BEFORE INSERT ON bookings
WHEN (SELECT status FROM rooms WHERE room_id = NEW.room_id) = 'MAINTENANCE'
BEGIN
    SELECT RAISE(ABORT, 'Room is under maintenance');
END;

-- 3. A room with upcoming bookings cannot be moved to maintenance.
CREATE TRIGGER IF NOT EXISTS trg_room_maintenance_guard
BEFORE UPDATE OF status ON rooms
WHEN NEW.status = 'MAINTENANCE' AND OLD.status <> 'MAINTENANCE'
BEGIN
    SELECT RAISE(ABORT, 'Room has upcoming bookings; cannot move to maintenance')
    WHERE EXISTS (
        SELECT 1 FROM bookings
        WHERE room_id = NEW.room_id
          AND status IN ('CONFIRMED', 'CHECKED_IN')
          AND check_out > date('now')
    );
END;

-- 4. Booking status is a state machine:
--    CONFIRMED -> CHECKED_IN -> CHECKED_OUT, or CONFIRMED -> CANCELLED
CREATE TRIGGER IF NOT EXISTS trg_booking_status_flow
BEFORE UPDATE OF status ON bookings
WHEN OLD.status <> NEW.status AND NOT (
        (OLD.status = 'CONFIRMED'  AND NEW.status IN ('CHECKED_IN', 'CANCELLED'))
     OR (OLD.status = 'CHECKED_IN' AND NEW.status = 'CHECKED_OUT'))
BEGIN
    SELECT RAISE(ABORT, 'Invalid booking status transition');
END;

-- 5. Ledger integrity for payments and refunds.
CREATE TRIGGER IF NOT EXISTS trg_payment_guard
BEFORE INSERT ON payments
BEGIN
    SELECT RAISE(ABORT, 'Cannot take a payment for a cancelled booking')
    WHERE NEW.kind = 'PAYMENT'
      AND (SELECT status FROM bookings WHERE booking_id = NEW.booking_id) = 'CANCELLED';

    SELECT RAISE(ABORT, 'Payment exceeds the outstanding balance')
    WHERE NEW.kind = 'PAYMENT'
      AND ROUND(NEW.amount + COALESCE((
              SELECT SUM(CASE kind WHEN 'PAYMENT' THEN amount ELSE -amount END)
              FROM payments WHERE booking_id = NEW.booking_id), 0), 2)
          > (SELECT total_amount FROM bookings WHERE booking_id = NEW.booking_id);

    SELECT RAISE(ABORT, 'Refund exceeds the amount paid')
    WHERE NEW.kind = 'REFUND'
      AND ROUND(NEW.amount, 2) > ROUND(COALESCE((
              SELECT SUM(CASE kind WHEN 'PAYMENT' THEN amount ELSE -amount END)
              FROM payments WHERE booking_id = NEW.booking_id), 0), 2);
END;

-- 6. Automatic audit trail.
CREATE TRIGGER IF NOT EXISTS trg_audit_booking_insert
AFTER INSERT ON bookings
BEGIN
    INSERT INTO audit_log(table_name, record_id, action, details)
    VALUES ('bookings', NEW.booking_id, 'CREATED',
            'room_id=' || NEW.room_id || ' ' || NEW.check_in || ' -> ' || NEW.check_out);
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_booking_status
AFTER UPDATE OF status ON bookings
WHEN OLD.status <> NEW.status
BEGIN
    INSERT INTO audit_log(table_name, record_id, action, details)
    VALUES ('bookings', NEW.booking_id, 'STATUS_CHANGE', OLD.status || ' -> ' || NEW.status);
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_payment
AFTER INSERT ON payments
BEGIN
    INSERT INTO audit_log(table_name, record_id, action, details)
    VALUES ('payments', NEW.booking_id, NEW.kind,
            printf('%.2f via %s', NEW.amount, NEW.method));
END;
