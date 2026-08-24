from datetime import datetime

import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def jalali_datetime(value):
    """Format a datetime like toLocaleString("fa") without seconds.

    Example: ۱۴۰۵/۶/۱, ۱۲:۳۰
    """
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return "-"
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    elif timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    jalali = jdatetime.datetime.fromgregorian(datetime=value)
    formatted = (
        f"{jalali.year}/{jalali.month}/{jalali.day}, "
        f"{jalali.hour}:{jalali.minute:02d}"
    )
    return formatted.translate(_PERSIAN_DIGITS)
