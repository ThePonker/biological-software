"""Key Species (status only): the workbook figure that leaves out species that are
Key only through a priority list or legal protection. The existing Key Species
figure must not change. Built from stub entries; no live data."""
from types import SimpleNamespace as S

import pytest

from Examen import workbook_export as we


def _e(**kw):
    base = dict(rarity="", threat="", threat_legacy="", priority=[], legal=[], tier="")
    base.update(kw)
    return S(**base)


CASES = [
    # (entry, telfer_tier, status_only_tier)
    (_e(rarity="NR", tier="Rare"), "rare", "rare"),
    (_e(threat="VU", tier="Rare"), "rare", "rare"),
    (_e(threat_legacy="RDB1", tier="Rare"), "rare", "rare"),
    (_e(rarity="NS", tier="Scarce"), "scarce", "scarce"),
    (_e(threat="NT", tier="Scarce"), "scarce", "scarce"),
    (_e(threat_legacy="Nb", tier="Scarce"), "scarce", "scarce"),
    # Key only because of S41: still Key, but not status-only.
    (_e(priority=["S41"], tier="Priority"), "scarce", ""),
    # Legally protected only: Codex gives such a species the Priority tier.
    (_e(legal=["Schedule 5"], tier="Priority"), "scarce", ""),
    # Specialist panel status (no code here) plus S41 or a legal listing: a status, so counted.
    (_e(priority=["S41"], tier="Scarce"), "scarce", "scarce"),
    (_e(legal=["Schedule 5"], tier="Scarce"), "scarce", "scarce"),
    # Priority tier with no list filled (Pantheon-only mode).
    (_e(tier="Priority"), "scarce", ""),
    # S41 and a rarity status: counted on the status.
    (_e(rarity="NS", priority=["S41"], tier="Scarce"), "scarce", "scarce"),
    (_e(threat="EN", priority=["S41"], tier="Rare"), "rare", "rare"),
    # A Codex Rare/Scarce tier from a code not in the sets is still a status.
    (_e(rarity="pRDB", tier="Rare"), "scarce", "scarce"),
    # Not an established native: never Key.
    (_e(threat="NA", rarity="NS", tier="Scarce"), "", ""),
    (_e(), "", ""),
]


@pytest.mark.parametrize("entry,telfer,status_only", CASES)
def test_tiers(entry, telfer, status_only):
    assert we.telfer_tier(entry) == telfer
    assert we.status_only_tier(entry) == status_only


def _summary(keys, total):
    openpyxl = pytest.importorskip("openpyxl")
    we._load_openpyxl()
    result = S(key_species=keys, total_species=total, merged_tvks=None,
               species_in_pantheon=total, derived_sqs_tvks=set(), species_with_sqs=total,
               rare_count=0, scarce_count=0, priority_count=0,
               overall_sqi=None,
               stenotopic_count=0)
    wb = openpyxl.Workbook()
    stamp = {"title": "T", "basis": [], "attribution": []}
    ws = we._sheet_summary(wb, result, S(species_list=[]), S(), stamp)
    return {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value
            for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=1).value}


def test_summary_rows_existing_figure_unchanged():
    keys = [_e(rarity="NR", tier="Rare"), _e(rarity="NS", tier="Scarce"),
            _e(priority=["S41"], tier="Priority"), _e(legal=["Schedule 5"], tier="Priority")]
    fig = _summary(keys, 40)
    assert fig["Key Species"] == 4
    assert fig["% Key Species"] == "10.0%"
    assert fig["Key Species (status only)"] == 2
    assert fig["% Key Species (status only)"] == "5.0%"
    assert fig["Rare Key Species"] == 1


def test_no_consultant_names_in_summary_notes():
    openpyxl = pytest.importorskip("openpyxl")
    we._load_openpyxl()
    result = S(key_species=[_e(rarity="NR", tier="Rare")], total_species=10,
               merged_tvks=None, species_in_pantheon=10, derived_sqs_tvks=set(),
               species_with_sqs=10, rare_count=0, scarce_count=0, priority_count=0,
               overall_sqi=None, stenotopic_count=0)
    ws = we._sheet_summary(openpyxl.Workbook(), result, S(species_list=[]), S(),
                           {"title": "T", "basis": [], "attribution": []})
    text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    for name in ("Telfer", "Kirby", "Wilson", "Jukes"):
        assert name not in text
