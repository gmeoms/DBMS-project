# Problem Statement

## Background
Small hotels often manage reservations in spreadsheets. This leads to **double bookings**,
unrecorded payments, wrong refunds and no history of who changed what.

## Objective
Build a terminal-based **Hotel Room Reservation System** whose core is a properly designed
relational database. The database, not the application code, is responsible for keeping
the data correct.

## Scope
- Staff login with roles (Admin / Receptionist)
- Rooms, room types and amenities (many-to-many)
- Guest registration and search
- Date-range bookings with overlap prevention
- Payments, refunds and outstanding balances
- Check-in / check-out life-cycle
- Reports: revenue, occupancy, top guests, audit trail

## Out of scope
Web or graphical front end, online payment gateways, multi-hotel chains.

## Target users
Hotel receptionists (daily operations) and the hotel manager (reports, configuration).

## DBMS concepts demonstrated
Normalization (3NF), primary/foreign keys, CHECK/UNIQUE/NOT NULL constraints,
M:N relationship, indexes, triggers, views, joins, subqueries, aggregation with GROUP BY/HAVING,
window functions, transactions (ACID), rollback, read-only access, query plans, audit logging.
