from datetime import date, datetime
from decimal import Decimal


def normalize_value(value):
    """Canonical form used to compare reference rows with agent rows."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 2)
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-" and text[:4].isdigit():
        return text[:10]
    try:
        return round(float(text), 2)
    except ValueError:
        return text.lower()


def normalize_row(values) -> list:
    return [normalize_value(v) for v in values]
