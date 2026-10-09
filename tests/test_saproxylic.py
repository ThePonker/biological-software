"""Examen saproxylic SQI and IEC (backlog E7, 9 Oct 2026)."""
from types import SimpleNamespace as S

import pytest

from Examen import saproxylic as sx


def sp(name, tvk=""):
    return S(name=name, tvk=tvk)


def test_the_list_loads_with_its_checked_links():
    by_tvk, by_name, genera = sx.load_list()
    assert set(genera) == {"melanotus", "leiopus"}
    assert sx.match("", "Carabus intricatus").sqi == 32
    # left out after the online check: Anaspis septentrionalis is a valid species,
    # so it must not score A. thoracica records
    assert sx.match("NBNSYS0000024918", "Anaspis thoracica").species == "Anaspis thoracica"
    assert sx.match("", "Anaspis septentrionalis") is None
    # old and current name both on the list: the current-name entry wins
    assert sx.match("NHMSYS0001718580", "Hypnogyra angularis").sqi == 8
    assert sx.match("", "Plagionotus arcuatus").sqi == 32          # spelling corrected
    assert sx.match("", "Melanotus villosus").species == "Melanotus"


def test_assess_arithmetic_and_counting_once():
    r = sx.assess([sp("Carabus intricatus"), sp("Carabus intricatus"),        # recorded twice
                   sp("Melanotus villosus"), sp("Melanotus castanipes"),      # one genus entry
                   sp("Hypnogyra angularis", "NHMSYS0001718580"),
                   sp("Pterostichus madidus")])                               # not saproxylic
    assert r.n_scored == 3 and r.sqs_total == 32 + 1 + 8
    assert r.sqi == round(41 * 100 / 3, 1)
    assert r.iec == 2 and r.n_iec == 1
    assert not r.reliable                                                     # < 40 species
    assert [b["met"] for b in r.sqi_bands] == [True, True, True]              # 1366.7
    assert "meets 300" in sx.band_text(r) and "IEC below 15" in sx.band_text(r)


def test_assess_nothing_listed():
    r = sx.assess([sp("Pterostichus madidus")])
    assert r.sqi is None and r.n_scored == 0 and r.summary.startswith("No species")


def test_workbook_sheet_reads_back_as_a_report_section():
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook
    from Examen import workbook_export as we
    from Examen import report_model as rm
    wb = Workbook()
    wb.remove(wb.active)
    detail = S(species_list=[sp("Carabus intricatus"), sp("Hypnogyra angularis", "NHMSYS0001718580")])
    ws = we._sheet_saproxylic(wb, detail)
    t = rm._table(ws)
    assert t["heads"] == ["Species", "Saproxylic score", "IEC", "Status (list)"]
    assert [r[0] for r in t["rows"]] == ["Carabus intricatus", "Hypnogyra angularis"]
    assert "Saproxylic Quality Index 2000" in t["subtitle"]
    assert any("side by side" in n for n in t["notes"])
    assert we._sheet_saproxylic(Workbook(), S(species_list=[sp("Pterostichus madidus")])) is None
