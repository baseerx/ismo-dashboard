"""Dates, the way this organisation counts them."""

from datetime import date, timedelta
from typing import Iterator, Tuple

# Pakistan financial year: 1 July -> 30 June. The leave entitlement in
# `leave_type_counts` is an allowance *per financial year*, so every balance
# calculation is scoped to one, exactly as the Django views do it.
FY_START_MONTH = 7

# Saturday, Sunday. `date.weekday()` numbering.
WEEKEND_DAYS = (5, 6)

# The standard working day the dashboard assesses attendance against.
CHECK_IN_DEADLINE = "08:30"
CHECK_OUT_DEADLINE = "16:00"


def financial_year(on: date | None = None) -> Tuple[date, date]:
    today = on or date.today()
    if today.month >= FY_START_MONTH:
        return date(today.year, 7, 1), date(today.year + 1, 6, 30)
    return date(today.year - 1, 7, 1), date(today.year, 6, 30)


def financial_year_label(start: date, end: date) -> str:
    return f"{start.year}-{end.year}"


def overlap_days(start: date, end: date, window_start: date, window_end: date) -> int:
    """Inclusive day count of [start, end] clipped into the window."""
    if not start or not end:
        return 0
    actual_start = max(start, window_start)
    actual_end = min(end, window_end)
    if actual_end < actual_start:
        return 0
    return (actual_end - actual_start).days + 1


def each_day(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def is_weekend(day: date) -> bool:
    return day.weekday() in WEEKEND_DAYS
