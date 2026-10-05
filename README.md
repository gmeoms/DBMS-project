# Hotel Room Reservation System (DBMS Project)

A terminal-based hotel reservation system in **Python + SQLite**. No frontend, no third-party
packages. The focus is database design: normalized schema, constraints, triggers, views,
transactions, indexes and analytical queries.

## Key features
1. **Staff accounts and roles**: Admin and Receptionist, salted password hashing.
2. **Rooms**: room types, rooms, amenities (many-to-many), maintenance status.
3. **Bookings**: date-range search, overlap prevention, weekend surcharge, long-stay discount.
4. **Payments**: deposits, balance tracking, automatic refunds by cancellation policy (100% / 50% / 0%).
5. **Life-cycle**: Confirmed → Checked-in → Checked-out (or Cancelled), enforced by the database.
6. **Reports**: net revenue, monthly cash flow, occupancy %, top guests, outstanding balances.
7. **Audit log** written automatically by triggers.
8. **Read-only SQL console** (admin) with `.tables`, `.schema`, and `explain`.
9. **Invoices** exported as `.txt`, and an ASCII availability calendar.

## Run
Requires Python 3.9+ (SQLite is built in).

```
python main.py            # first run creates data/hotel.db with demo data
python main.py --reset    # wipe and re-seed
python -m unittest discover -v
```

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Receptionist | `desk` | `desk123` |

Demo guest emails: `rajat@example.com`, `ananya@example.com`, `vikram@example.com`, `meera@example.com`.   

## Availability calendar preview
```
Room  04 05 06 07 08 09 10 11 12 13 14 15 16 17
      Su Mo Tu We Th Fr Sa Su Mo Tu We Th Fr Sa
101    .  .  .  .  .  .  .  .  .  .  .  .  .  .
103    .  .  .  .  .  .  .  .  .  .  #  #  .  .
201    .  .  .  #  #  #  .  .  .  .  .  .  .  .
301    @  @  @  .  .  .  .  .  .  .  .  .  .  .
Legend:  free   # booked   @ in house   M maintenance
```

## Structure  
 ```
.
├── main.py                 # entry point
├── statement.md            # problem statement and scope
├── docs/DESIGN.md          # ER diagram, normalization, triggers, transactions
├── sql/
│   ├── schema.sql          # tables, constraints, indexes
│   ├── triggers.sql        # business rules inside the DB
│   ├── views.sql           # reusable read models
│   └── seed.sql            # reference data
├── hotel/
│   ├── db.py               # connection + transaction() context manager
│   ├── auth.py  guests.py  rooms.py  bookings.py  reports.py
│   ├── seed.py             # demo data
│   ├── utils.py            # parsing / table formatting
│   └── cli.py              # terminal menus
└── tests/test_hotel.py     # 33 tests
```

## Where each DBMS concept lives
| Concept | Location |
|---------|----------|
| 3NF design, M:N table | `sql/schema.sql`, `docs/DESIGN.md` |
| CHECK / FK / UNIQUE | `sql/schema.sql` |
| Triggers (overlap, state machine, ledger, audit) | `sql/triggers.sql` |
| Views | `sql/views.sql` |
| Transactions + rollback | `hotel/db.py` `transaction()`, `bookings.cancel_booking` |
| Anti-join / NOT EXISTS | `rooms.find_available` |
| Window function, GROUP BY, clipping math | `reports.py` |
| Index + query plan | `schema.sql`, SQL console `explain` |
