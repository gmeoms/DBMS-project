-- Static reference data (staff users and sample bookings are added by seed.py)
INSERT INTO room_types(name, base_price, capacity) VALUES
    ('Standard', 2500, 2), ('Deluxe', 4000, 3), ('Suite', 8000, 4);

INSERT INTO rooms(room_number, floor, type_id)
SELECT n, CAST(substr(n,1,1) AS INTEGER), (SELECT type_id FROM room_types WHERE name = t)
FROM (SELECT '101' n, 'Standard' t UNION ALL SELECT '102','Standard'
      UNION ALL SELECT '103','Standard' UNION ALL SELECT '104','Standard'
      UNION ALL SELECT '201','Deluxe'   UNION ALL SELECT '202','Deluxe'
      UNION ALL SELECT '203','Deluxe'   UNION ALL SELECT '204','Deluxe'
      UNION ALL SELECT '301','Suite'    UNION ALL SELECT '302','Suite');

INSERT INTO amenities(name) VALUES ('WiFi'), ('AC'), ('TV'), ('Mini Bar'), ('Balcony'), ('Sea View');

-- every room: WiFi + AC + TV
INSERT INTO room_amenities
SELECT r.room_id, a.amenity_id FROM rooms r, amenities a WHERE a.name IN ('WiFi','AC','TV');
-- Deluxe & Suite: Mini Bar + Balcony
INSERT INTO room_amenities
SELECT r.room_id, a.amenity_id FROM rooms r
JOIN room_types rt ON rt.type_id = r.type_id, amenities a
WHERE rt.name IN ('Deluxe','Suite') AND a.name IN ('Mini Bar','Balcony');
-- Suite: Sea View
INSERT INTO room_amenities
SELECT r.room_id, a.amenity_id FROM rooms r
JOIN room_types rt ON rt.type_id = r.type_id, amenities a
WHERE rt.name = 'Suite' AND a.name = 'Sea View';

INSERT INTO guests(full_name, email, phone) VALUES
    ('Rajat Kumar',  'rajat@example.com',  '9876543210'),
    ('Ananya Sharma','ananya@example.com', '9123456780'),
    ('Vikram Singh', 'vikram@example.com', '9988776655'),
    ('Meera Iyer',   'meera@example.com',  NULL);
