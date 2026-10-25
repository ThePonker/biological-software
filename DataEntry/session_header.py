"""Session header model + helpers for DataEntry -- pure Python, NO Qt import.

Controlled-vocab sourcing (methods/stage/sex), kept Qt-free so it can be unit-tested
without a GUI.
"""
from __future__ import annotations


# ---- controlled-vocabulary sourcing -----------------------------------------

FALLBACK_METHODS = [
    "Field observation", "Pitfall trap", "Flight interception trap", "Malaise trap",
    "Water trap", "Yellow pan trap", "Light trap", "Beating", "Sweep net",
    "Suction sample", "Hand search", "Sieving", "Grubbing", "Direct search",
]
FALLBACK_STAGES = ["Adult", "Larva", "Nymph", "Pupa", "Egg", "Juvenile", "Not recorded"]
from shared.vocab import SEX_OPTIONS as FALLBACK_SEXES  # noqa: E402  (one sex list, R13)


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
