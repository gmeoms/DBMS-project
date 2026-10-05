"""Entry point:  python main.py [--db PATH] [--reset]"""
import argparse
from pathlib import Path

from hotel import cli, db, seed


def main():
    parser = argparse.ArgumentParser(description="Hotel Room Reservation System (SQLite)")
    parser.add_argument("--db", default=str(db.DEFAULT_DB), help="database file path")
    parser.add_argument("--reset", action="store_true", help="delete the database and re-seed demo data")
    args = parser.parse_args()

    if args.reset and Path(args.db).exists():
        Path(args.db).unlink()
    conn = db.connect(args.db)
    if seed.seed_if_empty(conn):
        print("First run: database created with demo data.")
    try:
        cli.run(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
