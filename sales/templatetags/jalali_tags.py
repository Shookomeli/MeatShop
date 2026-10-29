from django import template
from decimal import Decimal
from sales.date_utils import to_jalali_date, to_jalali_datetime, to_persian_digits, format_rial, format_thousands

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


@register.filter(name='rial')
def rial_filter(value_rial):
    """Stored Rial amount with Persian digits, thousands separators and unit: ۱۲,۵۰۰,۰۰۰ ریال."""
    return format_rial(value_rial)


@register.filter(name='thousands')
def thousands_filter(value):
    """Number only (Persian digits, thousands separators) for cells whose header names the unit."""
    return format_thousands(value)


@register.filter(name='toman_display')
def toman_display_filter(value_rial):
    """
    Approximate Toman hint only (Rial // 10), used under price-entry fields.
    Normal monetary displays use the `rial` / `thousands` filters.
    """
    if value_rial is None:
        return '۰'
    try:
        toman = int(value_rial) // 10
        return to_persian_digits(f"{toman:,}")
    except Exception:
        return to_persian_digits(str(value_rial))
