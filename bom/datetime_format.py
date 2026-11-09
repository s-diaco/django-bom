from datetime import datetime

import jdatetime
from django.utils import timezone

from bom.constants import CALENDAR_GREGORIAN, CALENDAR_JALALI


def _localize(value):
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return timezone.make_aware(value, timezone.get_current_timezone())


def format_datetime(value, calendar=CALENDAR_JALALI):
    """Format a datetime for display; Jalali calendar with Latin digits, no seconds.

    Jalali example: 1405/6/1, 12:30
    Gregorian example: 2026/8/23, 12:30
    """
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return "-"

    value = _localize(value)
    if calendar == CALENDAR_GREGORIAN:
        return f"{value.year}/{value.month}/{value.day}, {value.hour}:{value.minute:02d}"

    jalali = jdatetime.datetime.fromgregorian(datetime=value)
    return (
        f"{jalali.year}/{jalali.month}/{jalali.day}, "
        f"{jalali.hour}:{jalali.minute:02d}"
    )


def format_date(value, calendar=CALENDAR_JALALI):
    """Format a datetime as a date only; same calendar/locale path as format_datetime.

    Jalali example: 1405/6/1
    Gregorian example: 2026/8/23
    """
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return "-"

    value = _localize(value)
    if calendar == CALENDAR_GREGORIAN:
        return f"{value.year}/{value.month}/{value.day}"

    jalali = jdatetime.datetime.fromgregorian(datetime=value)
    return f"{jalali.year}/{jalali.month}/{jalali.day}"
