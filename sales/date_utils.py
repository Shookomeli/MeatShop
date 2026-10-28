import zoneinfo
from datetime import datetime, date, time
from typing import Optional, Tuple, Union
import jdatetime
from django.utils import timezone
from django.conf import settings

PERSIAN_DIGITS_TABLE = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
LATIN_DIGITS_TABLE = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
def get_tehran_tz():
    try:
        from django.conf import settings
        if settings.configured:
            return zoneinfo.ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Tehran'))
    except Exception:
        pass
    return zoneinfo.ZoneInfo('Asia/Tehran')


def to_persian_digits(value: Union[str, int, float]) -> str:
    """Converts Latin digits 0-9 to Persian digits ۰-۹."""
    if value is None:
        return ''
    return str(value).translate(PERSIAN_DIGITS_TABLE)


def to_latin_digits(value: str) -> str:
    """Converts Persian and Arabic digits to standard Latin ASCII 0-9 digits."""
    if not value:
        return ''
    return str(value).translate(LATIN_DIGITS_TABLE)


def to_jalali_date(value: Optional[Union[date, datetime]], fmt: str = '%Y/%m/%d', persian_digits: bool = True) -> str:
    """
    Converts a Python date or datetime to a formatted Jalali date string.
    Localizes datetimes to Asia/Tehran before conversion.
    """
    if not value:
        return ''
    tz = get_tehran_tz()
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value, tz)
        value = value.date()

    j_date = jdatetime.date.fromgregorian(date=value)
    formatted = j_date.strftime(fmt)
    return to_persian_digits(formatted) if persian_digits else formatted


def to_jalali_datetime(value: Optional[datetime], fmt: str = '%Y/%m/%d - %H:%M', persian_digits: bool = True) -> str:
    """
    Converts a Python datetime to a formatted Jalali datetime string in Asia/Tehran timezone.
    """
    if not value:
        return ''
    tz = get_tehran_tz()
    if timezone.is_aware(value):
        value = timezone.localtime(value, tz)
    else:
        value = value.replace(tzinfo=tz)

    j_dt = jdatetime.datetime.fromgregorian(datetime=value)
    formatted = j_dt.strftime(fmt)
    return to_persian_digits(formatted) if persian_digits else formatted


def parse_jalali_or_gregorian_date(date_str: str) -> Optional[date]:
    """
    Parses a date string in either Persian/Jalali (1300-1500) or Gregorian (>1900) format.
    Accepts separators '/' or '-' and Persian or Latin digits.
    Returns standard datetime.date object.
    Raises ValueError on invalid formats or dates.
    """
    if not date_str:
        return None

    cleaned = to_latin_digits(str(date_str).strip())
    # Replace slashes with dashes for uniform splitting
    normalized = cleaned.replace('/', '-')
    parts = normalized.split('-')

    if len(parts) != 3:
        raise ValueError(f"فرمت تاریخ نامعتبر است: {date_str}. لطفاً از الگوی YYYY/MM/DD استفاده نمایید.")

    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(f"مقادیر عددی تاریخ نامعتبر هستند: {date_str}")

    if 1300 <= y <= 1500:
        # Jalali calendar date (astronomically verified leap years and month boundaries via jdatetime)
        try:
            j_date = jdatetime.date(y, m, d)
            return j_date.togregorian()
        except ValueError as e:
            raise ValueError(f"تاریخ شمسی نامعتبر است: {date_str} ({str(e)})")
    elif y >= 1900:
        try:
            return date(y, m, d)
        except ValueError as e:
            raise ValueError(f"تاریخ میلادی نامعتبر است: {date_str} ({str(e)})")
    else:
        raise ValueError(f"سال تاریخ در محدوده معتبر نیست: {y}")


def get_tehran_date_range_bounds(start_date: Optional[date], end_date: Optional[date]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Translates date boundaries into timezone-aware datetime objects in Asia/Tehran:
    - start_date -> 00:00:00.000000
    - end_date -> 23:59:59.999999
    For safe inclusive range queries: `date_time__gte=start_dt, date_time__lte=end_dt`.
    """
    start_dt = None
    end_dt = None

    tz = get_tehran_tz()
    if start_date:
        start_naive = datetime.combine(start_date, time.min)
        start_dt = timezone.make_aware(start_naive, tz)

    if end_date:
        end_naive = datetime.combine(end_date, time.max)
        end_dt = timezone.make_aware(end_naive, tz)

    return start_dt, end_dt
