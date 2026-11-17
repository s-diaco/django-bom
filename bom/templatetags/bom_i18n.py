from django import template
from django.utils.translation import gettext as _

from bom.utils import currency_label as _currency_label
from bom.utils import format_money_amount

register = template.Library()


@register.filter(name="currency_label")
def currency_label(code):
    return _currency_label(code)


@register.simple_tag
def percent_unit():
    """Percent unit for two-row headers. Template `{% trans "%" %}` does not translate."""
    # Translators: unit under profit column headers (English "%", Persian "درصد")
    return _("%")


@register.filter(name="money_amount")
def money_amount(value):
    """Format a Money/Decimal as grouped digits without a currency code."""
    return format_money_amount(value)
