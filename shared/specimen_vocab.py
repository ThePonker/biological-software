"""specimen_vocab -- the curatorial lists a specimen is made with (25 Nov 2026).

Moved out of Add Specimen (Observatum/src/views/dialogs/add_specimen_dialog.py) so that
Make specimens (shared/make_specimens.py) uses the same lists and the same default
preparation: one home, no copy. No Qt. The dialog re-exports the four names.
"""
from __future__ import annotations

from typing import Optional

# Curatorial vocabularies -- edit these lists to change the dropdown options.
PREPARATION_TYPES = ["", "Pinned", "Carded", "Pointed", "In alcohol",
                     "Slide-mounted", "Genitalia prep"]
CONDITIONS = ["", "Good", "Damaged"]
STORAGE_LOCATIONS = ["", "Cabinet", "Useful Box", "Storage box"]

# Default preparation by taxonomic order (only applied to an empty field).
PREP_BY_ORDER = {
    "diptera": "Pinned",
    "hymenoptera": "Pinned",
    "coleoptera": "Carded",
}


# How the Insect Collection stores sex (Add Specimen's list). Records say "male", "Not recorded",
# "mixed" and so on; a specimen is one individual, so only Male / Female carry over.
_SEX = {"male": "Male", "m": "Male", "female": "Female", "f": "Female"}


def specimen_sex(value: Optional[str]) -> Optional[str]:
    """A record's sex as a specimen's: "Male", "Female", or None (not recorded, mixed, blank)."""
    return _SEX.get((value or "").strip().lower())


def default_prep_for_order(order: Optional[str]) -> str:
    """The preparation an order is usually kept as ('' when there is no rule)."""
    return PREP_BY_ORDER.get((order or "").strip().lower(), "")


__all__ = ["PREPARATION_TYPES", "CONDITIONS", "STORAGE_LOCATIONS", "PREP_BY_ORDER",
           "default_prep_for_order", "specimen_sex"]
