"""vocab -- the suite's shared controlled lists (R13, 24 Oct 2026).

One sex list for every entry point (Add Specimen, Quick Entry, Data Entry, the observation
import check). A blank choice is added where a drop-down needs one: SEX_CHOICES.
"""
from __future__ import annotations

SEX_OPTIONS = ["Female", "Male", "Mixed", "Not recorded"]
SEX_CHOICES = [""] + SEX_OPTIONS        # for drop-downs that allow leaving it blank

__all__ = ["SEX_OPTIONS", "SEX_CHOICES"]
