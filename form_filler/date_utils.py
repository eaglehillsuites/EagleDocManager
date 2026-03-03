"""
Form Filler Date Utils - All date calculations for the form filler feature.
"""

from datetime import date, timedelta
import calendar


MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

ORDINALS = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
    7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
    13: "13th", 14: "14th", 15: "15th", 16: "16th", 17: "17th",
    18: "18th", 19: "19th", 20: "20th", 21: "21st", 22: "22nd",
    23: "23rd", 24: "24th", 25: "25th", 26: "26th", 27: "27th",
    28: "28th", 29: "29th", 30: "30th", 31: "31st",
}


def ordinal_date_str(d: date) -> str:
    """Format a date as 'March 1st, 2026'."""
    return f"{MONTH_NAMES[d.month - 1]} {ORDINALS[d.day]}, {d.year}"


def month_year_str(d: date) -> str:
    """Format as 'August 2026'."""
    return f"{MONTH_NAMES[d.month - 1]} {d.year}"


def last_day_of_month(year: int, month: int) -> date:
    """Return the last day of a given month."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, last)


def last_day_of_next_next_month() -> date:
    """
    DueDate default: last day of the month AFTER the current one.
    e.g. if today is Feb 2026 → last day of March 2026 = March 31st.
    """
    today = date.today()
    # Advance two months
    month = today.month + 1
    year = today.year
    if month > 12:
        month -= 12
        year += 1
    return last_day_of_month(year, month)


def default_due_date() -> date:
    return last_day_of_next_next_month()


def default_delivery_date() -> date:
    return date.today()


def most_recent_past_month_start(month_index: int) -> date:
    """
    Given a month number (1-12), return the most recent past occurrence
    of the 1st of that month.

    Logic: renewals go out 3-4 months before lease end, so the lease
    start was in the past.

    e.g. today = Feb 2026, month_index = 8 (August) → Aug 1st, 2025
         today = Feb 2026, month_index = 1 (January) → Jan 1st, 2026
         today = Feb 2026, month_index = 2 (February) → Feb 1st, 2026
    """
    today = date.today()
    year = today.year

    candidate = date(year, month_index, 1)
    if candidate > today:
        candidate = date(year - 1, month_index, 1)

    return candidate


def lease_end_from_start(lease_start: date) -> date:
    """One day less than a year after lease start."""
    # One year later minus one day
    try:
        one_year = lease_start.replace(year=lease_start.year + 1)
    except ValueError:
        # Feb 29 edge case
        one_year = lease_start.replace(year=lease_start.year + 1, day=28)
    return one_year - timedelta(days=1)


def new_lease_end_from_end(lease_end: date) -> date:
    """New end of lease = lease_end + 1 year."""
    try:
        return lease_end.replace(year=lease_end.year + 1)
    except ValueError:
        return lease_end.replace(year=lease_end.year + 1, day=28)


def increase_date_from_lease_start(lease_start: date) -> date:
    """IncreaseDate = 1 year after lease start (same month/day, next year)."""
    try:
        return lease_start.replace(year=lease_start.year + 1)
    except ValueError:
        return lease_start.replace(year=lease_start.year + 1, day=28)


def parse_date_input(text: str) -> date | None:
    """Parse dd/mm/yyyy input string. Returns None if invalid."""
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return date(*[int(x) for x in __import__('datetime').datetime.strptime(text, fmt).timetuple()[:3]])
        except ValueError:
            continue
    return None


def format_for_field(d: date, style: str = "ordinal") -> str:
    """
    Format a date for insertion into a PDF field.
    style='ordinal' → 'March 1st, 2026'
    style='month_year' → 'March 2026'
    style='iso' → '2026-03-01'
    """
    if style == "ordinal":
        return ordinal_date_str(d)
    elif style == "month_year":
        return month_year_str(d)
    elif style == "iso":
        return d.strftime("%Y-%m-%d")
    return str(d)
