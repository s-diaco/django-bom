"""Birthday surprise helpers: parse admin date entry, match month/day in local TZ."""

from __future__ import annotations

import re
from datetime import date, datetime

import jdatetime
from django.core.exceptions import ValidationError
from django.utils import timezone

# Years below this are treated as Jalali when a full date is entered.
_JALALI_YEAR_MAX = 1700

_DATE_RE = re.compile(
    r"^\s*(\d{1,4})[/.\-](\d{1,2})(?:[/.\-](\d{1,2}))?\s*$"
)


def parse_birthday_input(value: str) -> tuple[int, int] | None:
    """Parse admin birthday entry into Gregorian (month, day).

    Accepts:
    - ``YYYY/MM/DD`` or ``YYYY-MM-DD`` — year < 1700 ⇒ Jalali (converted);
      otherwise Gregorian. Year is used only for calendar detection / conversion.
    - ``MM/DD`` — Gregorian month/day.
    - Empty / whitespace ⇒ ``None`` (clear birthday).
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    match = _DATE_RE.match(text)
    if not match:
        raise ValidationError(
            "Enter a date as YYYY/MM/DD (Gregorian or Jalali) or MM/DD (Gregorian)."
        )

    a, b, c = match.group(1), match.group(2), match.group(3)
    if c is None:
        month, day = int(a), int(b)
        _validate_month_day(month, day)
        return month, day

    year, month, day = int(a), int(b), int(c)
    if year < _JALALI_YEAR_MAX:
        try:
            g = jdatetime.date(year, month, day).togregorian()
        except ValueError as exc:
            raise ValidationError(f"Invalid Jalali date: {text}") from exc
        return g.month, g.day

    try:
        date(year, month, day)
    except ValueError as exc:
        raise ValidationError(f"Invalid Gregorian date: {text}") from exc
    return month, day


def _validate_month_day(month: int, day: int) -> None:
    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 1 and 12.")
    # Leap year so Feb 29 is allowed; match only fires on an actual Feb 29.
    try:
        date(2000, month, day)
    except ValueError as exc:
        raise ValidationError(f"Invalid month/day: {month}/{day}") from exc


def format_birthday_md(month: int | None, day: int | None) -> str:
    if not month or not day:
        return ""
    return f"{month}/{day}"


def today_local(when: date | datetime | None = None) -> date:
    """Return today's date in the active Django timezone (Asia/Tehran by default)."""
    if when is None:
        return timezone.localdate()
    if isinstance(when, datetime):
        if timezone.is_aware(when):
            return timezone.localtime(when).date()
        return timezone.make_aware(when, timezone.get_current_timezone()).date()
    return when


def matches_birthday(
    birthday_month: int | None,
    birthday_day: int | None,
    on_date: date | datetime | None = None,
) -> bool:
    if not birthday_month or not birthday_day:
        return False
    today = today_local(on_date)
    return today.month == birthday_month and today.day == birthday_day
