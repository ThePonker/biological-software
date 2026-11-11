"""Round 19: the redesigned Home tab. Tiny purpose-made databases in tmp_path; nothing from the
live data is pinned. Offscreen."""
import os
import sqlite3
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.repositories.codex_repository import (  # noqa: E402
    CodexRepository, NOTABLE_STATUS_ORDER, notable_status)

YEAR = date.today().year
OBS_DDL = ("CREATE TABLE observations (id INTEGER PRIMARY KEY, record_type TEXT, species_name TEXT, "
           "common_name TEXT, species_tvk TEXT, taxon_rank TEXT, date TEXT, date_type TEXT, "
           "grid_ref TEXT, site_name TEXT, embargo_status TEXT, embargo_until TEXT, "
           "vice_county TEXT, vc_number INTEGER, recorder TEXT, quantity TEXT, order_name TEXT, "
           "family TEXT, taxon_group TEXT, kingdom TEXT, project_name TEXT, client TEXT, comment TEXT, "
           "internal_notes TEXT, sample_comment TEXT, identification_remarks TEXT, "
           "verification_status TEXT, sample_method TEXT, determiner TEXT, irecord_id TEXT)")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def counting_defaults(monkeypatch):
    import shared.species_counting as sc
    monkeypatch.setattr(sc, "excluded_kinds", lambda source: frozenset())


def _obs_db(tmp_path, rows):
    """rows: (record_type, name, tvk, date, grid_ref, site)."""
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.executescript(OBS_DDL + ";CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, grid_ref TEXT);")
    for rt, name, tvk, d, gr, site in rows:
        c.execute("INSERT INTO observations (record_type, species_name, species_tvk, taxon_rank, date, "
                  "date_type, grid_ref, site_name) VALUES (?,?,?,?,?,'D',?,?)",
                  (rt, name, tvk, "Species", d, gr, site))
    c.commit()
    c.close()
    return str(p)


def _codex(tmp_path, statuses):
    """A tiny codex + uksi: statuses = [(tvk, track, value)]; every tvk an invertebrate."""
    tvks = sorted({t for t, _, _ in statuses})
    u = sqlite3.connect(tmp_path / "uksi.db")
    u.execute("CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, "
              "parent_tvk TEXT, kingdom TEXT, phylum TEXT)")
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?)",
                  [(t, t, "Species", None, "Animalia", "Arthropoda") for t in tvks])
    u.commit()
    u.close()
    c = sqlite3.connect(tmp_path / "codex.db")
    c.executescript("""
        CREATE TABLE designations (tvk TEXT, category TEXT);
        CREATE TABLE status_summary (tvk TEXT, status_track TEXT, status_value TEXT,
            status_detail TEXT, source TEXT, iucn_version TEXT);
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT DEFAULT 'pantheon');
        CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT);
        CREATE TABLE tvk_bridge (pantheon_tvk TEXT PRIMARY KEY, uksi_tvk TEXT,
            species_name TEXT, match_method TEXT);""")
    c.executemany("INSERT INTO status_summary VALUES (?,?,?,NULL,'test','')", statuses)
    c.commit()
    c.close()
    return CodexRepository(str(tmp_path / "codex.db"), str(tmp_path / "none.db"),
                           uksi_path=str(tmp_path / "uksi.db"))


# ------------------------------------------------------------------ Home layout
def test_home_builds_without_quick_entry(qapp):
    from src.views.home.home_tab import HomeTab
    from src.views.home.quick_entry import QuickEntryForm
    h = HomeTab()
    assert not hasattr(h, "quick_entry")
    assert not h.findChildren(QuickEntryForm)
    from PySide6.QtWidgets import QLabel
    texts = {lab.text() for lab in h.findChildren(QLabel)}
    assert "Dropdown Options Reference" not in texts
    assert not any("QUICK SINGLE OBSERVATION" in t.upper() for t in texts)
    for name in ("map_card", "species_info", "recent_panel", "notable_card"):
        assert getattr(h, name) is not None


def test_stats_cards_have_no_last_month_rows(qapp):
    from src.views.home.home_tab import HomeTab
    h = HomeTab()
    for card in h._observation_cards():
        assert "last_month_records" not in card.rows
        assert len(card.rows) == 4
    from PySide6.QtWidgets import QLabel
    assert not any("Last Month" in lab.text() for lab in h.findChildren(QLabel))


# ------------------------------------------------------------------ the map's squares
AMARA, HIPPO = "NBNSYS0000007359", "NBNSYS0000008315"     # Amara fulva, Hippodamia variegata (UKSI)


def test_hectad_squares_this_year_all_years_and_one_species(tmp_path):
    import paths
    from src.views.home import home_data as hd
    if not paths.UKSI_DB.exists():
        pytest.skip("UKSI copy not present (the species choice reads it, as Mapping does)")
    rows = [("Personal", "Aus bus", AMARA, f"{YEAR}-05-01", "SP5820", "x")] * 10 \
        + [("Commercial", "Cus dus", HIPPO, f"{YEAR}-05-02", "SP581201", "x")] \
        + [("Personal", "Aus bus", "TA", f"{YEAR}-06-01", "TQ3080", "y")] * 100 \
        + [("Personal", "Aus bus", "TA", f"{YEAR - 1}-06-01", "SU1020", "z")] \
        + [("Personal", "Aus bus", "TA", f"{YEAR}-06-01", "SP58", "coarse")]   # 10 km ref: its own square
    db = _obs_db(tmp_path, rows)
    cur = hd.hectad_squares(db, hd.THIS_YEAR)
    assert set(cur) == {"SP52", "TQ38", "SP58"}
    assert cur["SP52"]["count"] == 11 and cur["SP52"]["class"] == 1      # 10-99 (Personal + Commercial)
    assert cur["TQ38"]["count"] == 100 and cur["TQ38"]["class"] == 2     # 100+
    alltime = hd.hectad_squares(db, hd.ALL_YEARS)
    assert "SU12" in alltime and alltime["SU12"] == {"count": 1, "class": 0}   # 1-9
    assert "SU12" not in cur
    # one species: only the squares of its records (its own TVK, all years)
    sp = hd.hectad_squares(db, hd.SELECTED, tvk=HIPPO, name="Hippodamia variegata")
    assert set(sp) == {"SP52"} and sp["SP52"]["count"] == 1
    assert hd.hectad_squares(db, hd.SELECTED) == {}                       # none chosen


def test_record_classes():
    from src.views.home.home_data import record_class
    assert [record_class(n) for n in (1, 9, 10, 99, 100, 5000)] == [0, 0, 1, 1, 2, 2]


# ------------------------------------------------------------------ last 10 new species
def test_last_new_species_order_ties_by_date_then_name():
    from src.views.home.home_data import last_new_species

    class Repo:
        def get_new_species_first_records(self, limit=10):
            rows = [("Zeta", "2026-07-01"), ("Alpha", "2026-07-01"), ("Mid", "2026-08-01"),
                    ("Beta", "2026-07-01")] + [(f"Old{i:02d}", f"2020-01-{i + 1:02d}") for i in range(12)]
            return [{"species_name": n, "date": d, "site_name": "S", "order_name": "Coleoptera",
                     "species_tvk": n, "common_name": ""} for n, d in rows]
    out = last_new_species(Repo())
    assert [r["species_name"] for r in out[:4]] == ["Mid", "Alpha", "Beta", "Zeta"]
    assert len(out) == 10 and out[0]["short_date"] == "1 Aug" and out[0]["group"] == "Beetles"


def test_last_new_species_from_a_tiny_db(tmp_path, qapp, monkeypatch):
    from src.models.database import get_database
    from src.repositories import ObservationRepository
    from src.views.home.home_data import last_new_species
    rows = [("Personal", "Aus bus", "TA", "2020-01-01", "SP5820", "x"),
            ("Personal", "Aus bus", "TA", "2026-03-01", "SP5820", "x"),     # not its first
            ("Personal", "Bus cus", "TB", "2026-02-01", "SP5820", "y"),
            ("Commercial", "Cus dus", "TC", "2026-02-01", "SP5820", "z")]
    path = _obs_db(tmp_path, rows)
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(path)
    try:
        out = last_new_species(ObservationRepository())
    finally:
        db._main_db_path, db._uksi_db_path = old
    assert [r["species_name"] for r in out] == ["Bus cus", "Cus dus", "Aus bus"]


# ------------------------------------------------------------------ notable
def test_notable_status_excludes_nt_includes_ns_and_picks_highest(tmp_path):
    codex = _codex(tmp_path, [
        ("T_NT", "threat_iucn_2001", "NT"), ("T_LC", "threat_iucn_2001", "LC"),
        ("T_NS", "rarity_modern", "NS"), ("T_VU", "threat_iucn_2001", "VU"),
        ("T_BOTH", "rarity_modern", "NS"), ("T_BOTH", "threat_iucn_2001", "EN"),
        ("T_RDB", "threat_iucn_legacy", "RDB3"), ("T_NA", "rarity_modern", "NR"),
        ("T_NA", "threat_iucn_2001", "NA"), ("T_DD", "threat_iucn_2001", "DD"),
        ("T_PRI", "priority", "NERC S.41 England"), ("T_NB", "rarity_legacy", "Nb")])
    st = codex.get_statuses_batch(["T_NT", "T_LC", "T_NS", "T_VU", "T_BOTH", "T_RDB", "T_NA", "T_DD",
                                   "T_PRI", "T_NB"])
    got = {t: notable_status(s) for t, s in st.items()}
    assert got == {"T_NT": None, "T_LC": None, "T_NS": "NS", "T_VU": "VU", "T_BOTH": "EN",
                   "T_RDB": "RDB3", "T_NA": None, "T_DD": None, "T_PRI": None, "T_NB": "Nb"}
    assert st["T_NT"].is_key                     # the report rule still counts NT; Home does not
    assert NOTABLE_STATUS_ORDER.index("CR") < NOTABLE_STATUS_ORDER.index("NS")
    codex.close()


def test_notable_records_filter_sort_and_personal_only(tmp_path):
    from src.views.home import home_data as hd
    codex = _codex(tmp_path, [("T_NT", "threat_iucn_2001", "NT"), ("T_NS", "rarity_modern", "NS"),
                              ("T_CR", "threat_iucn_2001", "CR"), ("T_NB", "rarity_legacy", "Nb")])
    rows = [("Personal", "Nt one", "T_NT", f"{YEAR}-08-01", "SP5820", "a"),
            ("Personal", "Ns one", "T_NS", f"{YEAR}-07-01", "SP5820", "b"),
            ("Commercial", "Cr one", "T_CR", f"{YEAR}-06-01", "SP5820", "c"),
            ("Personal", "Nb one", "T_NB", f"{YEAR}-09-01", "SP5820", "d"),
            ("Personal", "Ns old", "T_NS", f"{YEAR - 1}-07-01", "SP5820", "e")]   # last year
    db = _obs_db(tmp_path, rows)
    newest = hd.notable_records(db, codex=codex)
    assert newest["total"] == 3 and len(newest["ids"]) == 3
    assert [r["species_name"] for r in newest["rows"]] == ["Nb one", "Ns one", "Cr one"]
    assert [r["status"] for r in newest["rows"]] == ["Nb", "NS", "CR"]
    best = hd.notable_records(db, sort=hd.HIGHEST, codex=codex)
    assert [r["status"] for r in best["rows"]] == ["CR", "NS", "Nb"]
    personal = hd.notable_records(db, personal_only=True, codex=codex)
    assert [r["species_name"] for r in personal["rows"]] == ["Nb one", "Ns one"]
    assert personal["total"] == 2
    codex.close()


def test_notable_rows_are_one_per_species_with_a_count(tmp_path):
    from src.views.home import home_data as hd
    codex = _codex(tmp_path, [("T_NS", "rarity_modern", "NS")])
    rows = [("Personal", "Ns one", "T_NS", f"{YEAR}-07-01", "SP5820", "b"),
            ("Personal", "Ns one", "T_NS", f"{YEAR}-08-03", "SP5821", "c"),
            ("Personal", "Ns one", "T_NS", f"{YEAR}-06-01", "SP5822", "d")]
    out = hd.notable_records(_obs_db(tmp_path, rows), codex=codex)
    assert out["total"] == 3 and len(out["ids"]) == 3 and out["species"] == 1
    assert len(out["rows"]) == 1 and out["rows"][0]["n"] == 3
    assert out["rows"][0]["date"] == f"{YEAR}-08-03"            # its latest record
    codex.close()


def test_notable_card_toggles_reload_with_their_choices(qapp, monkeypatch):
    from src.views.home import home_lists
    calls = []
    monkeypatch.setattr(home_lists.hd, "notable_records",
                        lambda path, personal_only=False, sort="newest": calls.append((personal_only, sort))
                        or {"total": 0, "ids": [], "rows": []})
    monkeypatch.setattr(home_lists.JobRunner, "start", lambda self, fn, done: done(fn()))
    card = home_lists.NotableCard()
    card.set_database("x.db")
    card.reload()
    card.highest_btn.click()
    card.personal_btn.click()
    card.newest_btn.click()
    assert calls == [(False, "newest"), (False, "highest"), (True, "highest"), (True, "newest")]


def test_notable_all_link_emits_the_ids(qapp):
    from src.views.home.home_lists import NotableCard
    card = NotableCard()
    got = []
    card.all_clicked.connect(got.append)
    card.show_data({"total": 2, "ids": [4, 9], "rows": [
        {"id": 4, "status": "NS", "species_name": "A b", "common_name": "", "site_name": "s",
         "grid_ref": "SP1", "date": f"{YEAR}-01-02", "short_date": "2 Jan"},
        {"id": 9, "status": "CR", "species_name": "C d", "common_name": "", "site_name": "",
         "grid_ref": "", "date": "", "short_date": ""}]})
    assert card.all_btn.text() == "All 2 records"
    card.all_btn.click()
    assert got == [[4, 9]]
