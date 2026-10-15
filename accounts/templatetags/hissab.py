from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def mru(value):
    """1234567.5 -> '1 234 567,50' ; whole numbers drop the decimals."""
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    text = f"{number:,.0f}" if number == number.to_integral_value() else f"{number:,.2f}"
    return text.replace(",", " ").replace(".", ",")


@register.filter
def pct(value):
    try:
        return f"{Decimal(value) * 100:.0f} %"
    except (InvalidOperation, TypeError, ValueError):
        return value
