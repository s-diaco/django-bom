from decimal import ROUND_HALF_UP, Decimal

from django import template

from bom.constants import UNIT_COST_DECIMAL_PLACES
from bom.utils import currency_label as _currency_label

register = template.Library()


@register.filter(name="currency_label")
def currency_label(code):
    return _currency_label(code)


@register.filter(name="money_amount")
def money_amount(value):
    """Format a Money/Decimal as grouped digits without a currency code."""
    if value is None or value == "":
        return ""
    amount = value.amount if hasattr(value, "amount") else value
    try:
        amount = Decimal(amount)
    except Exception:
        return value
    quant = (
        Decimal("1").scaleb(-UNIT_COST_DECIMAL_PLACES)
        if UNIT_COST_DECIMAL_PLACES
        else Decimal("1")
    )
    amount = amount.quantize(quant, rounding=ROUND_HALF_UP)
    if UNIT_COST_DECIMAL_PLACES == 0:
        return f"{int(amount):,}"
    return f"{amount:,.{UNIT_COST_DECIMAL_PLACES}f}"
