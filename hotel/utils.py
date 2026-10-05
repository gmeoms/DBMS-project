"""Small helpers: date parsing, money formatting, table printing."""
from datetime import date

from .db import HotelError


def parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise HotelError(f"Invalid date '{value}' (use YYYY-MM-DD)") from None


def money(amount):
    return f"Rs {amount:,.2f}"


def format_table(rows, headers=None):
    """Render sqlite3.Row objects (or dicts) as an aligned text table."""
    rows = list(rows)
    if not rows:
        return "  (no rows)"
    headers = list(headers or rows[0].keys())

    def cell(v):
        if v is None:
            return ""
        return f"{v:,.2f}" if isinstance(v, float) else str(v)

    body = [[cell(r[h]) for h in headers] for r in rows]
    widths = [max(len(h), *(len(line[i]) for line in body)) for i, h in enumerate(headers)]
    fmt = "  ".join("{:<%d}" % w for w in widths)
    out = [fmt.format(*headers), "  ".join("-" * w for w in widths)]
    out += [fmt.format(*line) for line in body]
    return "\n".join(out)
