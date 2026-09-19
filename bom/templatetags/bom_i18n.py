from django import template

from bom.utils import currency_label as _currency_label

register = template.Library()


@register.filter(name="currency_label")
def currency_label(code):
    return _currency_label(code)
