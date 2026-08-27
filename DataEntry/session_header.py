"""Session header model + helpers for DataEntry -- pure Python, NO Qt import.

The SessionHeader holds the sticky values set once in the picker; per the build-ready
addendum (26a §4) every field is picker-set and later inline-overridable. This module also
holds the smart date parser and the controlled-vocab sourcing (methods/stage/sex), kept
Qt-free so they can be unit-tested without a GUI.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass


@dataclass
class SessionHeader:
    mode: str = "Personal"           # Personal | Commercial
    date: str = ""                   # ISO yyyy-mm-dd when concrete
    date_raw: str = ""               # kept verbatim when not a concrete date (year/range)
    site_name: str = ""
    grid_ref: str = ""
    vice_county: str = ""            # manual for now; auto-derives from grid ref in a later step
    vc_number: str = ""
    recorder: str = ""
    determiner: str = ""
    method: str = ""
    stage_default: str = "Adult"
    sub_location: str = ""           # internal (not exported to iRecord)
    trap_number: str = ""            # internal
    visit_number: str = ""           # internal
    # Commercial-only
    project_name: str = ""
    client: str = ""
    embargo_until: str = ""

    def is_commercial(self) -> bool:
        return self.mode.strip().lower() == "commercial"

    def has_concrete_date(self) -> bool:
        return bool(self.date)

    def date_display(self) -> str:
        return self.date or self.date_raw or "(none)"


def parse_date(text: str):
    """Smart date parse. Returns (iso, raw).

    Concrete dates resolve to ISO in slot 1 (raw empty). Non-concrete input (bare year,
    ranges, unparseable) is kept verbatim in slot 2 rather than silently coerced.
    """
    t = (text or "").strip()
    if not t:
        return "", ""
    low = t.lower()
    today = _dt.date.today()
    if low in ("today", "now"):
        return today.isoformat(), ""
    if low == "yesterday":
        return (today - _dt.timedelta(days=1)).isoformat(), ""

    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat(), ""
        except ValueError:
            return "", t

    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", t)  # UK day-first
    if m:
        try:
            return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat(), ""
        except ValueError:
            return "", t

    return "", t  # bare year, range, or anything else -> keep as typed


# ---- controlled-vocabulary sourcing -----------------------------------------

FALLBACK_METHODS = [
    "Field observation", "Pitfall trap", "Flight interception trap", "Malaise trap",
    "Water trap", "Yellow pan trap", "Light trap", "Beating", "Sweep net",
    "Suction sample", "Hand search", "Sieving", "Grubbing", "Direct search",
]
FALLBACK_STAGES = ["Adult", "Larva", "Nymph", "Pupa", "Egg", "Juvenile", "Not recorded"]
FALLBACK_SEXES = ["Female", "Male", "Mixed", "Not recorded"]


def load_vocab(attr: str, fallback):
    """Return (values, source). Try Observatum's src.utils.constants.<attr>; else fallback."""
    for modpath in ("src.utils.constants", "Observatum.src.utils.constants"):
        try:
            mod = __import__(modpath, fromlist=[attr])
            vals = getattr(mod, attr, None)
            if vals:
                return list(vals), f"{modpath}.{attr}"
        except Exception:
            continue
    return list(fallback), f"fallback ({attr} not found)"


def load_methods():
    return load_vocab("SAMPLE_METHOD_OPTIONS", FALLBACK_METHODS)


def load_stages():
    return load_vocab("STAGE_OPTIONS", FALLBACK_STAGES)


def load_sexes():
    return load_vocab("SEX_OPTIONS", FALLBACK_SEXES)
