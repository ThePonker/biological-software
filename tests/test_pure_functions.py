"""Pure functions the suite relies on -- pinned so a change that alters them shows up.

    py -3.14 -m pytest tests            (pip install pytest, once)

Backlog I6, 8 October 2026. No database is opened; every test runs in well under a
second. Where a test pins behaviour that looks odd, the comment says why it is kept.
"""
import datetime as dt

import pytest

from DataEntry import date_utils
from DataEntry.commit_service import DOUBLE_KEY, build_kwargs_from_row, precommit_issues
from shared.display_format import dmy, mode_label
from shared.sex_summary import classify_sex, count_sexes, format_sex_summary, label_with_sexes
from shared.species_rank import rank_matches
from shared.sqs_derivation import VALID_SCORES, derive_from_tracks, derive_sqs

TODAY = dt.date.today()


# ---------------------------------------------------------------- DataEntry/date_utils
@pytest.mark.parametrize("typed, iso", [
    ("05/06/2026", "2026-06-05"),        # dd/mm, never mm/dd
    ("5/6/2026", "2026-06-05"),
    ("05.06.2026", "2026-06-05"),
    ("05-06-2026", "2026-06-05"),
    ("05/06/26", "2026-06-05"),          # two-digit year -> 2000s
    ("2026-06-05", "2026-06-05"),
    ("2026-6-5", "2026-06-05"),
    ("  2026-06-05 ", "2026-06-05"),
    ("29/02/2024", "2024-02-29"),
])
def test_to_iso_accepts(typed, iso):
    assert date_utils.to_iso(typed) == iso


@pytest.mark.parametrize("typed", [None, "", "  ", "31/02/2026", "13/13/2026", "29/02/2025",
                                   "June 2026", "2026", "05/06", "abc"])
def test_to_iso_rejects(typed):
    assert date_utils.to_iso(typed) is None


def test_to_iso_words():
    assert date_utils.to_iso("Today") == TODAY.isoformat()
    assert date_utils.to_iso("yesterday") == (TODAY - dt.timedelta(days=1)).isoformat()


def test_normalise_keeps_what_it_cannot_read():
    assert date_utils.normalise("05/06/2026") == "2026-06-05"
    assert date_utils.normalise("summer 2026") == "summer 2026"   # left for the user to see


def test_is_future():
    assert date_utils.is_future((TODAY + dt.timedelta(days=1)).isoformat())
    assert not date_utils.is_future(TODAY.isoformat())
    assert not date_utils.is_future("not a date")


@pytest.mark.parametrize("value, shown", [
    ("2026-06-05", "05/06/2026"), (None, ""), ("", ""), ("05/06/2026", "05/06/2026"),
    ("2026-02-31", "2026-02-31"),          # impossible ISO date shown as typed
])
def test_to_display(value, shown):
    assert date_utils.to_display(value) == shown


# ---------------------------------------------------------------- shared/display_format
def test_dmy():
    assert dmy("2026-05-05") == "05/05/2026"
    assert dmy("2026-10-06 13:08") == "06/10/2026"     # datetime -> date part
    assert dmy(None) == ""
    assert dmy("Spring") == "Spring"


def test_mode_label():
    class Mode:                       # stands in for the AnalysisMode enum
        value = "pantheon_only"
    assert mode_label("codex_full") == "Codex Full"
    assert mode_label(Mode()) == "Pantheon Only"
    assert mode_label("something_new") == "something_new"
    assert mode_label(None) == ""


# ---------------------------------------------------------------- shared/sqs_derivation
@pytest.mark.parametrize("kw, score", [
    (dict(native=False, rarity="NR", threat="CR"), 0),
    (dict(), 1),
    (dict(threat="LC"), 1),
    (dict(threat="NT"), 1),                          # NT alone does not elevate
    (dict(threat="DD"), 1),                          # nor DD
    (dict(rarity="NS"), 4),
    (dict(rarity="Na"), 4),
    (dict(rarity="Nb"), 4),
    (dict(rarity="Notable"), 4),
    (dict(rarity="NS", threat="NT"), 4),
    (dict(rarity="NR"), 8),
    (dict(rarity="NR", threat="DD"), 8),             # 8 from the rarity, not the DD
    (dict(rarity="NS", threat="VU"), 8),
    (dict(threat="VU"), 8),                          # a VU listing is a listing
    (dict(threat_legacy="RDB2"), 8),
    (dict(threat_legacy="RDB3"), 8),
    (dict(threat_legacy="RDBK"), 4),                 # RDB K/I caps a rare species at 4
    (dict(rarity="NR", threat_legacy="RDBI"), 4),
    (dict(rarity="NS", threat="EN"), 16),
    (dict(threat_legacy="RDB1"), 16),
    (dict(rarity="NR", threat="CR"), 32),
    (dict(threat="RE"), 32),
    (dict(threat="Critically Endangered"), 32),
    (dict(threat_legacy="RDB App"), 32),
    (dict(rarity=" nr ", threat=" vu "), 8),         # case and spaces ignored
])
def test_derive_sqs(kw, score):
    assert derive_sqs(**kw) == score


def test_derive_sqs_never_leaves_the_published_ladder():
    rarities = [None, "NR", "NS", "Na", "Nb", "Notable", "rubbish"]
    threats = [None, "CR", "EN", "VU", "NT", "LC", "DD", "RE", "EX", "rubbish"]
    legacy = [None, "RDB1", "RDB2", "RDB3", "RDBK", "RDBI", "RDB App", "rubbish"]
    for r in rarities:
        for t in threats:
            for tl in legacy:
                assert derive_sqs(r, t, tl) in VALID_SCORES
    assert 2 not in VALID_SCORES                      # there is no 2 in the published rule


def test_derive_from_tracks_precedence():
    # modern rarity beats legacy rarity
    assert derive_from_tracks({"rarity_modern": "NR", "rarity_legacy": "Nb"}) == 8
    assert derive_from_tracks({"rarity_legacy": "Nb"}) == 4
    assert derive_from_tracks({"rarity_modern": "NS", "threat_iucn_2001": "EN"}) == 16
    assert derive_from_tracks({}, native=False) == 0


# ---------------------------------------------------------------- shared/species_rank
def _names(results):
    return [r["scientific_name"] for r in results]


def test_rank_matches_tiers():
    results = [{"scientific_name": n} for n in (
        "Leptura maculata",       # tier 3 for "rut mac"
        "Maculinea rutila",       # tier 1: both prefixes, wrong order
        "Rutpela maculata",       # tier 0: genus then epithet
        "Rutilus rutilus",        # tier 2: genus only
    )]
    assert _names(rank_matches("rut mac", results)) == [
        "Rutpela maculata", "Maculinea rutila", "Rutilus rutilus", "Leptura maculata"]


def test_rank_matches_recorded_first_within_a_tier_then_alphabetical():
    results = [{"scientific_name": "Bombus terrestris"},
               {"scientific_name": "Bombus pascuorum", "is_recorded": True},
               {"scientific_name": "Bombus lapidarius"}]
    assert _names(rank_matches("bom", results)) == [
        "Bombus pascuorum", "Bombus lapidarius", "Bombus terrestris"]


def test_rank_matches_empty_text_keeps_everything():
    results = [{"scientific_name": "B a"}, {"scientific_name": "A b"}, {"scientific_name": None}]
    assert len(rank_matches("", results)) == 3


# ---------------------------------------------------------------- shared/sex_summary
@pytest.mark.parametrize("stored, kind", [
    ("Male", "m"), ("male", "m"), ("M", "m"), ("♂", "m"),
    ("Female", "f"), ("F", "f"), ("female", "f"), ("♀", "f"),
    ("Unknown", None), ("", None), (None, None), ("Not recorded", None),
])
def test_classify_sex(stored, kind):
    assert classify_sex(stored) == kind


def test_count_and_format():
    assert count_sexes(["Male", "Female", "female", None, "Unknown"]) == (1, 2, 2)
    assert format_sex_summary(3, 4, 0) == "♂3 ♀4"
    assert format_sex_summary(2, 1, 4) == "♂2 ♀1 +4"
    assert format_sex_summary(0, 0, 7) == ""                 # nothing sexed: say nothing
    assert label_with_sexes("Spec.", 3, 4) == "Spec. 7 (♂3 ♀4)"
    assert label_with_sexes("Spec.", 0, 0, 7) == "Spec. 7"


# ---------------------------------------------------------------- DataEntry/commit_service
def _row(**kw):
    base = dict(species_name="Philanthus triangulum", species_tvk="NBNSYS0000012345",
                date="2026-06-05", site_name="Elmley", grid_ref="TQ9368",
                method="Sweep", trap_number="", sex="", stage="Adult")
    base.update(kw)
    return base


def test_precommit_issues_clean_job_is_empty():
    assert precommit_issues([_row(), _row(species_name="Odynerus spinipes")]) == {}


def test_precommit_issues_reports_grid_row_numbers():
    rows = [
        _row(),                                   # 1
        _row(site_name=" "),                      # 2  no site
        _row(grid_ref=None, species_tvk=""),      # 3  no grid ref, no TVK, not a double of 1
        _row(species_name=""),                    # 4  not committable: ignored
        _row(date=""),                            # 5  not committable: ignored
        _row(sex=""),                             # 6  double of 1
        _row(sex="Female"),                       # 7  a sex split is not a double
        _row(species_name="philanthus triangulum ", method="sweep"),   # 8  double of 1 (case, spaces)
    ]
    assert precommit_issues(rows) == {
        "no site": [2],
        "no grid ref": [3],
        "no TVK": [3],
        "double": [(2, 1), (6, 1), (8, 1)],
    }


def test_double_key_is_the_one_the_batch_check_uses():
    # scripts/check_data_entry_batches.py imports this; a field dropped here changes both
    assert DOUBLE_KEY == ("species_name", "date", "grid_ref", "method", "trap_number", "sex", "stage")


def test_build_kwargs_commercial_and_personal():
    job = {"mode": "Commercial", "client": "BAM", "project": "Glory Park"}
    row = _row(date="05/06/2026", quantity="0", vc_number="15")
    kw = build_kwargs_from_row(row, job, "2027-06-05")
    assert kw["date"] == "2026-06-05"
    assert kw["quantity"] == 1                  # never below 1
    assert kw["vc_number"] == 15
    assert kw["record_type"] == "Commercial"
    assert (kw.get("project_name"), kw.get("client"), kw.get("embargo_until")) == (
        "Glory Park", "BAM", "2027-06-05")

    kw = build_kwargs_from_row(_row(quantity="x", vc_number="VC15"), {"mode": "Personal",
                                                                       "client": "BAM"}, "2027-01-01")
    assert kw["quantity"] == 1
    assert kw["vc_number"] is None
    assert kw.get("client") is None and kw.get("embargo_until") is None   # personal: none of these


# ---------------------------------------------------------------- vc_lookup_service grid refs
from Observatum.src.services.vc_lookup_service import VCLookupService as VC  # noqa: E402


@pytest.mark.parametrize("ref, parsed", [
    ("SP58", (450000, 280000, 10000)),
    ("SP5820", (458000, 220000, 1000)),
    ("SP580207", (458000, 220700, 100)),
    ("SP58002070", (458000, 220700, 10)),
    ("SP5800020700", (458000, 220700, 1)),
    ("sp 580 207", (458000, 220700, 100)),
    ("SO539092", (353900, 209200, 100)),      # Highbury Wood (fault F29)
    ("TQ9368", (593000, 168000, 1000)),
    ("HU4039", (440000, 1139000, 1000)),      # Shetland
    ("SV9010", (90000, 10000, 1000)),         # Scilly
])
def test_parse_grid_ref(ref, parsed):
    assert VC.parse_grid_ref(ref) == parsed


@pytest.mark.parametrize("ref", [None, "", "SP5", "SP58020", "XX5820", "S58020", "SP58A0", "TQ"])
def test_parse_grid_ref_rejects(ref):
    assert VC.parse_grid_ref(ref) is None


@pytest.mark.parametrize("ref, square", [
    ("SP580207", "SP5820"), ("SP5800020799", "SP5820"), ("SO539092", "SO5309"),
    ("SO539069", "SO5306"), ("SP5820", "SP5820"),
    ("SP58", "SP5080"),     # a 10 km ref resolves to its south-west 1 km square
])
def test_get_1km_square(ref, square):
    assert VC.get_1km_square(ref) == square


# ---------------------------------------------------------------- Observatum specimen sort key
def test_taxonomic_sort_key():
    pytest.importorskip("PySide6")          # Observatum.src.utils imports Qt on the way in
    from Observatum.src.utils.constants import compute_taxonomic_sort_key
    assert compute_taxonomic_sort_key("Coleoptera", 1234) < compute_taxonomic_sort_key("Diptera", 1)
    assert compute_taxonomic_sort_key("Hymenoptera", 5) == 26_000_005
    assert compute_taxonomic_sort_key("Araneae", None) == 99_000_000    # not an insect order: last


# ---------------------------------------------------------------- Examen taxonomic order (E19)
def test_in_taxonomic_order(monkeypatch):
    from types import SimpleNamespace as NS
    from Examen import examen_data
    keys = {"T1": 5_000_500, "T2": 26_000_010, "T3": 5_000_100}     # beetles before wasps
    monkeypatch.setattr(examen_data, "taxonomic_sort_keys", lambda tvks: keys)
    items = [NS(tvk="T2", name="Philanthus"), NS(tvk="", name="no TVK"),
             NS(tvk="T1", name="Rutpela"), NS(tvk="T9", name="Absent from UKSI"),
             NS(tvk="T3", name="Carabus")]
    assert [x.name for x in examen_data.in_taxonomic_order(items)] == [
        "Carabus", "Rutpela", "Philanthus", "Absent from UKSI", "no TVK"]
