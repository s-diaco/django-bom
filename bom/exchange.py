"""Manual FX rates backed by djmoney's Rate / ExchangeBackend tables.

Convention: backend base_currency is the organization currency. Each Rate row
stores ``value`` = organization-currency units per 1 unit of ``Rate.currency``
(e.g. IRR per 1 USD). This matches how users enter bank rates and avoids the
lossy inverse that stock ``convert_money`` expects when base is the org currency.
"""

from decimal import Decimal

from django.utils import timezone
from djmoney.contrib.exchange.models import ExchangeBackend, Rate
from djmoney.money import Money


MANUAL_BACKEND_NAME = "manual"


class ManualExchangeBackend:
    """Placeholder backend so djmoney's default backend name is ``manual``."""

    name = MANUAL_BACKEND_NAME


class MissingExchangeRate(Exception):
    """Raised when no manual rate exists for a foreign currency."""


def get_manual_backend(base_currency):
    backend, _ = ExchangeBackend.objects.update_or_create(
        name=MANUAL_BACKEND_NAME,
        defaults={
            "base_currency": str(base_currency),
            "last_update": timezone.now(),
        },
    )
    if backend.base_currency != str(base_currency):
        backend.base_currency = str(base_currency)
        backend.last_update = timezone.now()
        backend.save(update_fields=["base_currency", "last_update"])
    return backend


def get_org_per_unit_rate(foreign_currency, org_currency):
    """Return org-currency units per 1 foreign unit, or None if unset."""
    foreign_currency = str(foreign_currency)
    org_currency = str(org_currency)
    if foreign_currency == org_currency:
        return Decimal("1")
    backend = get_manual_backend(org_currency)
    rate = Rate.objects.filter(backend=backend, currency=foreign_currency).first()
    return rate.value if rate is not None else None


def get_all_org_per_unit_rates(org_currency):
    """Return {foreign_code: rate_or_None} for import currencies except org."""
    from bom.constants import IMPORT_CURRENCY_CODES

    org_currency = str(org_currency)
    return {
        code: get_org_per_unit_rate(code, org_currency)
        for code in IMPORT_CURRENCY_CODES
        if code != org_currency
    }


def set_org_per_unit_rate(foreign_currency, org_currency, value):
    """Upsert or delete a manual rate (org currency per 1 foreign unit)."""
    foreign_currency = str(foreign_currency)
    org_currency = str(org_currency)
    backend = get_manual_backend(org_currency)
    if value is None or value == "":
        Rate.objects.filter(backend=backend, currency=foreign_currency).delete()
        return None
    value = Decimal(value)
    rate, _ = Rate.objects.update_or_create(
        backend=backend,
        currency=foreign_currency,
        defaults={"value": value},
    )
    backend.last_update = timezone.now()
    backend.save(update_fields=["last_update"])
    return rate


def convert_to_org_currency(money, org_currency):
    """Convert a Money value into organization currency using manual rates."""
    if money is None:
        return None
    org_currency = str(org_currency)
    if str(money.currency) == org_currency:
        return money
    rate = get_org_per_unit_rate(money.currency, org_currency)
    if rate is None:
        raise MissingExchangeRate(
            f"No exchange rate for {money.currency} → {org_currency}. "
            "Set it in Settings."
        )
    return Money(money.amount * rate, org_currency)
