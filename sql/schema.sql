-- =====================================================================
-- schema.sql : tables, constraints and indexes (3NF)
-- Safe to run repeatedly (IF NOT EXISTS everywhere).
-- =====================================================================

CREATE TABLE IF NOT EXISTS users (          -- hotel staff who log in
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN', 'RECEPTIONIST')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS room_types (
    type_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    base_price REAL NOT NULL CHECK (base_price > 0),
    capacity   INTEGER NOT NULL CHECK (capacity BETWEEN 1 AND 10)
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT NOT NULL UNIQUE,
    floor       INTEGER NOT NULL CHECK (floor >= 0),
    type_id     INTEGER NOT NULL
                REFERENCES room_types(type_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    status      TEXT NOT NULL DEFAULT 'AVAILABLE'
                CHECK (status IN ('AVAILABLE', 'MAINTENANCE'))
);

CREATE TABLE IF NOT EXISTS amenities (
    amenity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE
);

-- Many-to-many: a room has many amenities, an amenity is in many rooms
CREATE TABLE IF NOT EXISTS room_amenities (
    room_id    INTEGER NOT NULL REFERENCES rooms(room_id)         ON DELETE CASCADE,
    amenity_id INTEGER NOT NULL REFERENCES amenities(amenity_id)  ON DELETE CASCADE,
    PRIMARY KEY (room_id, amenity_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS guests (
    guest_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name  TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email      TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (email LIKE '%_@_%._%'),
    phone      TEXT CHECK (phone IS NULL OR phone GLOB '[0-9+]*'),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id     INTEGER NOT NULL REFERENCES guests(guest_id) ON DELETE RESTRICT,
    room_id      INTEGER NOT NULL REFERENCES rooms(room_id)   ON DELETE RESTRICT,
    check_in     TEXT NOT NULL CHECK (check_in  GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    check_out    TEXT NOT NULL CHECK (check_out GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status       TEXT NOT NULL DEFAULT 'CONFIRMED'
                 CHECK (status IN ('CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED')),
    total_amount REAL NOT NULL CHECK (total_amount >= 0),   -- price snapshot at booking time
    created_by   INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (check_out > check_in)
);

CREATE TABLE IF NOT EXISTS payments (        -- ledger: payments and refunds
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(booking_id) ON DELETE RESTRICT,
    kind       TEXT NOT NULL DEFAULT 'PAYMENT' CHECK (kind IN ('PAYMENT', 'REFUND')),
    amount     REAL NOT NULL CHECK (amount > 0),
    method     TEXT NOT NULL CHECK (method IN ('CASH', 'CARD', 'UPI')),
    paid_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (       -- filled automatically by triggers
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id  INTEGER NOT NULL,
    action     TEXT NOT NULL,
    details    TEXT,
    logged_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes: the overlap check and availability search filter by room + dates
CREATE INDEX IF NOT EXISTS idx_bookings_room_dates ON bookings(room_id, check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_guest      ON bookings(guest_id);
CREATE INDEX IF NOT EXISTS idx_payments_booking    ON payments(booking_id);
CREATE INDEX IF NOT EXISTS idx_rooms_type          ON rooms(type_id);
