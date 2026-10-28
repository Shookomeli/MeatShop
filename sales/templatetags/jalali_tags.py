from django import template
from decimal import Decimal
from sales.date_utils import to_jalali_date, to_jalali_datetime, to_persian_digits

register = template.Library()


@register.filter(name='jdate')
def jdate_filter(value, fmt='%Y/%m/%d'):
    """Formats date or datetime to Jalali date with Persian digits."""
    return to_jalali_date(value, fmt=fmt, persian_digits=True)


@register.filter(name='jdatetime')
def jdatetime_filter(value, fmt='%Y/%m/%d - %H:%M'):
    """Formats datetime to Jalali datetime in Asia/Tehran timezone with Persian digits."""
    return to_jalali_datetime(value, fmt=fmt, persian_digits=True)


@register.filter(name='fa_digits')
def fa_digits_filter(value):
    """Converts 0-9 digits in any string or number to Persian ۰-۹ digits."""
    return to_persian_digits(value)


@register.filter(name='format_weight_kg')
def format_weight_kg_filter(value):
    """Formats decimal weight to 3 decimal places with Persian digits."""
    if value is None:
        return '۰.۰۰۰'
    try:
        dec = Decimal(str(value))
        formatted = f"{dec:.3f}"
        return to_persian_digits(formatted)
    except Exception:
        return to_persian_digits(str(value))


@register.filter(name='toman_display')
def toman_display_filter(value_rial):
    """Converts whole Rial integer to Toman with comma separation and Persian digits."""
    if value_rial is None:
        return '۰'
    try:
        toman = int(value_rial) // 10
        return to_persian_digits(f"{toman:,}")
    except Exception:
        return to_persian_digits(str(value_rial))
