-- =====================================================================
-- views.sql : reusable read models
-- =====================================================================

CREATE VIEW IF NOT EXISTS v_booking_details AS
SELECT b.booking_id,
       g.full_name  AS guest,
       g.email      AS email,
       r.room_number,
       rt.name      AS room_type,
       b.check_in,
       b.check_out,
       CAST(julianday(b.check_out) - julianday(b.check_in) AS INTEGER) AS nights,
       b.status,
       b.total_amount,
       COALESCE((SELECT SUM(CASE p.kind WHEN 'PAYMENT' THEN p.amount ELSE -p.amount END)
                 FROM payments p WHERE p.booking_id = b.booking_id), 0) AS net_paid
FROM bookings b
JOIN guests g      ON g.guest_id = b.guest_id
JOIN rooms r       ON r.room_id  = b.room_id
JOIN room_types rt ON rt.type_id = r.type_id;

CREATE VIEW IF NOT EXISTS v_revenue_by_room_type AS
SELECT rt.name AS room_type,
       COUNT(DISTINCT b.booking_id) AS bookings,
       COALESCE(SUM(CASE p.kind WHEN 'PAYMENT' THEN p.amount
                                WHEN 'REFUND'  THEN -p.amount END), 0) AS net_revenue
FROM room_types rt
LEFT JOIN rooms r    ON r.type_id = rt.type_id
LEFT JOIN bookings b ON b.room_id = r.room_id
LEFT JOIN payments p ON p.booking_id = b.booking_id
GROUP BY rt.type_id;

CREATE VIEW IF NOT EXISTS v_outstanding_balances AS
SELECT booking_id, guest, room_number, status, total_amount, net_paid,
       ROUND(total_amount - net_paid, 2) AS balance_due
FROM v_booking_details
WHERE status IN ('CONFIRMED', 'CHECKED_IN')
  AND ROUND(total_amount - net_paid, 2) > 0;
