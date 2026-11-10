"""The Mapping tab's date-range check (MAP3, L9, R9-4), kept apart from the filter panel.

date_problems(from_text, to_text) -> ([what is wrong], {'From': iso or None, 'To': iso or
None}, reversed). Each box reads a year (2020), a month (06/2020) or a day (01/06/2020 or
ISO) through shared.import_core.date_bounds; From takes the start of its period, To the end,
so From 2019 / To 2019 is the whole of 2019 and From 2021 / To 2019 is reversed.
"""
from typing import Dict, List, Optional, Tuple

from shared.import_core import date_bounds
from shared.maps.map_stats import DECADES


def decade_choices() -> List[Tuple[str, str, str]]:
    """[(label, From text, To text)] for the Date Range's Decade choice: the very bands the
    export page's "Records by decade" line uses (map_stats.DECADES), open-ended at either end
    ("pre-1950" has no From, "2020\u2013" no To)."""
    return [(label, str(lo) if lo else "", str(hi) if hi else "") for label, lo, hi in DECADES]


def reversed_text(from_text: str, to_text: str) -> str:
    return f"From ({from_text.strip()}) is after To ({to_text.strip()}): swap them or change one."


def date_problems(from_text: str, to_text: str
                  ) -> Tuple[List[str], Dict[str, Optional[str]], bool]:
    bad: List[str] = []
    bounds: Dict[str, Optional[str]] = {}
    for name, text, end in (("From", from_text, False), ("To", to_text, True)):
        text = (text or "").strip()
        if not text:
            bounds[name] = None
            continue
        b = date_bounds(text)
        if b is None:
            bad.append(f"{name} date '{text}' not understood: use 2020, 06/2020 or 01/06/2020.")
            bounds[name] = None
        else:
            bounds[name] = b[1] if end else b[0]
    backwards = bool(bounds["From"] and bounds["To"] and bounds["From"] > bounds["To"])
    if backwards:
        bad.append(reversed_text(from_text, to_text))
    return bad, bounds, backwards
