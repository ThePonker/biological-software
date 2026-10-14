"""Natural sort key for table columns (no Qt).

Blank last (ascending), numbers numerically, other text naturally and
case-insensitively with digit runs compared as numbers.
"""
import re
from functools import lru_cache

_NUMBER = re.compile(r'^[+-]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$|^[+-]?\.\d+$')
_DIGITS = re.compile(r'(\d+)')


def sort_key(value):
    """Return a tuple that orders any two values without a TypeError."""
    if value is None:
        return (1,)
    if isinstance(value, (int, float)):
        if value != value:                       # NaN counts as blank
            return (1,)
        return (0, 1, ((0, float(value), ''),))
    return _text_key(str(value))


@lru_cache(maxsize=65536)
def _text_key(raw: str):
    """A number is a one-part natural key, so "2" < "2a" < "3" < "10" (review 14 Oct 2026);
    cached, as large tables compare the same values many times."""
    text = raw.strip()
    if not text:
        return (1,)
    if _NUMBER.match(text):
        return (0, 1, ((0, float(text.replace(',', '')), ''),))
    parts = []
    for i, bit in enumerate(_DIGITS.split(text.lower())):
        if i % 2:
            parts.append((0, int(bit), ''))
        elif bit:
            parts.append((1, 0, bit))
    return (0, 1, tuple(parts))


def less_than(a, b):
    """True when a sorts before b under the natural key."""
    return sort_key(a) < sort_key(b)
