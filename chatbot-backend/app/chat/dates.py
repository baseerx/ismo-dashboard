"""Turning "last month" or "1 Jul to 15 Aug" into two dates.

Date handling is done here, in code, rather than left to the language model.
A model that mis-reads a range produces a confident, wrong report, and the
person reading it has no way to tell. A regex either matches or it does not,
and every answer states the range it actually used so the reader can check.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from re import error
from typing import Optional

from app.hr.calendar import financial_year, financial_year_label

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))

# 2026-08-15 | 15/08/2026 | 15-08-2026 | 15.8.26
_ISO = r"(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})"
_DMY = r"(?P<d>\d{1,2})[-/.](?P<m>\d{1,2})[-/.](?P<y>\d{2,4})"
# 15 August 2026 | 15th Aug | August 15, 2026 | Aug 2026
_DAY_MONTH = rf"(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<mon>{MONTH_NAMES})\.?(?:\s+(?P<y>\d{{4}}))?"
_MONTH_DAY = rf"(?P<mon>{MONTH_NAMES})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<y>\d{{4}}))?"
_MONTH_ONLY = rf"(?P<mon>{MONTH_NAMES})\.?(?:\s+(?P<y>\d{{4}}))?"
# "15 August" / "3rd Sep" - a month with a day in front of it is one date,
# not a whole month.
_DAY_BEFORE_MONTH = rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTH_NAMES})"

_DATE_PATTERNS = (_ISO, _DMY, _DAY_MONTH, _MONTH_DAY)


def _anonymise(pattern: str) -> str:
    """Same pattern with its group names dropped.

    The four date patterns all name their groups `d`/`m`/`y`, so they can only
    be combined into one alternation once the names are gone - a regex cannot
    define the same group name twice. Matched text is handed back to
    `_parse_single`, which applies the named patterns one at a time.
    """
    return re.sub(r"\(\?P<\w+>", "(?:", pattern)


_SINGLE_DATE = "(?:" + "|".join(_anonymise(p) for p in _DATE_PATTERNS) + ")"

_RANGE_JOINER = r"\s*(?:to|until|till|through|thru|-|–|—|and)\s*"


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date
    label: str
    # True when the question actually named a period. False means a default
    # was applied, which the answer says out loud rather than implying the
    # user asked for it.
    explicit: bool = True

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def clamped(self, max_days: int) -> "DateRange":
        if self.days <= max_days:
            return self
        return DateRange(
            start=self.end - timedelta(days=max_days - 1),
            end=self.end,
            label=f"{self.label} (trimmed to the last {max_days} days)",
            explicit=self.explicit,
        )

    def until_today(self, today: Optional[date] = None) -> "DateRange":
        """Trim a period that runs past today.

        "attendance in August" asked on the 18th must not report the rest of the
        month as absent - there is no attendance record for a day that has not
        happened.
        """
        today = today or date.today()
        if self.end <= today:
            return self
        if self.start > today:
            return self
        return DateRange(self.start, today, f"{self.label} up to today", self.explicit)

    def describe(self) -> str:
        if self.start == self.end:
            return self.start.strftime("%d %b %Y")
        return f"{self.start.strftime('%d %b %Y')} to {self.end.strftime('%d %b %Y')}"


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _normalise_year(raw: Optional[str], today: date) -> int:
    if not raw:
        return today.year
    value = int(raw)
    if value < 100:
        value += 2000
    return value


def _from_match(match: re.Match, today: date) -> Optional[date]:
    """Build a date out of whichever named groups a pattern filled in."""

    def group(name: str) -> Optional[str]:
        try:
            return match.group(name)
        except (IndexError, error):
            return None

    day = group("d")
    month_word = group("mon")
    month_num = group("m")
    year = _normalise_year(group("y"), today)

    if month_word:
        month = MONTHS[month_word.lower().rstrip(".")]
    elif month_num:
        month = int(month_num)
    else:
        return None

    if not 1 <= month <= 12:
        return None

    if day is None:
        return date(year, month, 1)

    day_value = int(day)
    last = calendar.monthrange(year, month)[1]
    if not 1 <= day_value <= last:
        return None

    return date(year, month, day_value)


def _explicit_range(text: str, today: date) -> Optional[DateRange]:
    """"from 1 Jul to 15 Aug", "between 2026-07-01 and 2026-07-31"."""
    pattern = re.compile(
        rf"(?:from\s+|between\s+)?(?P<a>{_SINGLE_DATE}){_RANGE_JOINER}(?P<b>{_SINGLE_DATE})",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        first = _parse_single(match.group("a"), today)
        second = _parse_single(match.group("b"), today)
        if not first or not second:
            continue

        # "1 Jul to 15 Aug" - the first date carries no year of its own, so it
        # inherits the second one's rather than defaulting to this year.
        if not re.search(r"\d{4}", match.group("a")) and re.search(r"\d{4}", match.group("b")):
            try:
                first = first.replace(year=second.year)
            except ValueError:
                pass

        start, end = sorted((first, second))
        return DateRange(start, end, f"{start:%d %b %Y} to {end:%d %b %Y}")

    return None


def _parse_single(text: str, today: date) -> Optional[date]:
    text = text.strip()
    for pattern in _DATE_PATTERNS:
        match = re.fullmatch(pattern, text, re.IGNORECASE)
        if match:
            return _from_match(match, today)
    return None


def _month_range(text: str, today: date) -> Optional[DateRange]:
    """"in August", "for August 2026", "Aug 2026" - a whole month."""
    # "on 15 August 2026" names one day; let the single-date parser have it.
    if re.search(_DAY_BEFORE_MONTH, text, re.IGNORECASE):
        return None

    match = re.search(
        rf"\b(?:in|for|of|during)?\s*\b{_MONTH_ONLY}\b(?!\s*\d{{1,2}}\b)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    month = MONTHS[match.group("mon").lower().rstrip(".")]
    year = _normalise_year(match.group("y"), today)

    # "in August" asked in February means last August, not one six months out.
    if not match.group("y") and month > today.month:
        year -= 1

    start = date(year, month, 1)
    return DateRange(start, _month_end(year, month), f"{start:%B %Y}")


def _relative_range(text: str, today: date) -> Optional[DateRange]:
    lowered = text.lower()

    def rolling(days: int, label: str) -> DateRange:
        return DateRange(today - timedelta(days=days - 1), today, label)

    if re.search(r"\btoday\b|\btoday's\b", lowered):
        return DateRange(today, today, "today")

    if re.search(r"\byesterday\b", lowered):
        day = today - timedelta(days=1)
        return DateRange(day, day, "yesterday")

    match = re.search(r"\b(?:last|past|previous|recent)\s+(\d{1,3})\s*(day|week|month)s?\b", lowered)
    if match:
        count = int(match.group(1))
        unit = match.group(2)
        if unit == "day":
            return rolling(count, f"the last {count} days")
        if unit == "week":
            return rolling(count * 7, f"the last {count} week(s)")
        return rolling(count * 30, f"the last {count} month(s)")

    if re.search(r"\bthis week\b|\bcurrent week\b", lowered):
        start = today - timedelta(days=today.weekday())
        return DateRange(start, today, "this week")

    if re.search(r"\blast week\b|\bprevious week\b|\bpast week\b", lowered):
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        return DateRange(start, start + timedelta(days=6), "last week")

    if re.search(r"\bthis month\b|\bcurrent month\b", lowered):
        start = today.replace(day=1)
        return DateRange(start, today, f"{start:%B %Y} so far")

    if re.search(r"\blast month\b|\bprevious month\b|\bpast month\b", lowered):
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        return DateRange(end.replace(day=1), end, f"{end:%B %Y}")

    if re.search(r"\b(?:this|current)\s+(?:financial|fiscal)\s+year\b|\bthis fy\b|\bcurrent fy\b", lowered):
        start, end = financial_year(today)
        return DateRange(start, end, f"financial year {financial_year_label(start, end)}")

    if re.search(r"\b(?:last|previous)\s+(?:financial|fiscal)\s+year\b|\blast fy\b", lowered):
        start, end = financial_year(today)
        start = start.replace(year=start.year - 1)
        end = end.replace(year=end.year - 1)
        return DateRange(start, end, f"financial year {financial_year_label(start, end)}")

    if re.search(r"\bthis year\b|\bcurrent year\b", lowered):
        return DateRange(date(today.year, 1, 1), today, f"{today.year} so far")

    if re.search(r"\blast year\b|\bprevious year\b", lowered):
        year = today.year - 1
        return DateRange(date(year, 1, 1), date(year, 12, 31), str(year))

    if re.search(r"\bthis quarter\b", lowered):
        quarter_start_month = 3 * ((today.month - 1) // 3) + 1
        return DateRange(date(today.year, quarter_start_month, 1), today, "this quarter")

    return None


def _single_day(text: str, today: date) -> Optional[DateRange]:
    """"on 15 August", "attendance for 2026-08-03"."""
    match = re.search(_SINGLE_DATE, text, re.IGNORECASE)
    if not match:
        return None

    day = _parse_single(match.group(0), today)
    if not day:
        return None

    return DateRange(day, day, day.strftime("%d %b %Y"))


def parse_date_range(text: str, today: Optional[date] = None) -> Optional[DateRange]:
    """The first reading that matches, most specific pattern first.

    Returns None when the question named no period at all, leaving the choice
    of default to the caller.
    """
    today = today or date.today()
    text = text or ""

    for parser in (_explicit_range, _relative_range, _month_range, _single_day):
        found = parser(text, today)
        if found:
            return found

    return None


def default_range(today: Optional[date] = None) -> DateRange:
    """What "my leaves" means with no period given: the financial year."""
    today = today or date.today()
    start, end = financial_year(today)
    return DateRange(
        start,
        end,
        f"financial year {financial_year_label(start, end)}",
        explicit=False,
    )
