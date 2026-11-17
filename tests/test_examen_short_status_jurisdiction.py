"""Examen species list: a priority listing from another country is not shown (17 Nov 2026)."""
from types import SimpleNamespace as NS

from Examen.examen_data import short_status_for


def _st(short, *values):
    return NS(short_status=short, priority=[NS(value=v) for v in values])


def test_scottish_list_only_is_blank_in_england():
    assert short_status_for(_st("Priority", "Scottish Biodiversity List"), "England") == ""


def test_section_41_is_named_in_england():
    assert short_status_for(_st("Priority", "NERC Act Section 41"), "England") == "S41"


def test_scottish_list_shows_in_scotland():
    assert short_status_for(_st("Priority", "Scottish Biodiversity List"), "Scotland") == "SBL"


def test_other_statuses_unchanged():
    assert short_status_for(_st("NS"), "England") == "NS"
    assert short_status_for(None, "England") == ""
