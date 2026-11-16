"""Round 20: the Home tab's map (recorded or not, the Show list), the Year list and the
fixed-height species card. Small purpose-made databases in tmp_path; nothing from live data."""
import os
import sqlite3
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

YEAR = date.today().year
DDL = ("CREATE TABLE observations (id INTEGER PRIMARY KEY, record_type TEXT, species_name TEXT, "
       "common_name TEXT, species_tvk TEXT, taxon_rank TEXT, date TEXT, date_type TEXT, "
       "grid_ref TEXT, site_name TEXT, embargo_status TEXT, embargo_until TEXT, vice_county TEXT, "
       "vc_number INTEGER, recorder TEXT, quantity TEXT, order_name TEXT, family TEXT, "
       "taxon_group TEXT, kingdom TEXT, project_name TEXT, client TEXT, comment TEXT, "
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


@pytest.fixture
def sync_jobs(monkeypatch):
    from src.views.home.home_worker import JobRunner
    monkeypatch.setattr(JobRunner, "start", lambda self, fn, done: done(fn()))


def make_db(tmp_path, rows, name="observatum.db"):
    """rows: (record_type, species, tvk, date, date_type, grid_ref)."""
    p = tmp_path / name
    c = sqlite3.connect(p)
    c.executescript(DDL + ";CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, grid_ref TEXT);")
    for rt, sp, tvk, d, dt, gr in rows:
        c.execute("INSERT INTO observations (record_type, species_name, species_tvk, taxon_rank, date, "
                  "date_type, grid_ref, site_name) VALUES (?,?,?,?,?,?,?,'x')",
                  (rt, sp, tvk, "Species", d, dt, gr))
    c.commit()
    c.close()
    return str(p)


# ------------------------------------------------------------------ the map: recorded or not
def test_squares_have_no_count_classes(tmp_path):
    from src.views.home import home_data as hd
    rows = [("Personal", "A a", "TA", f"{YEAR}-05-01", "D", "SP5820")] * 120 \
        + [("Personal", "B b", "TB", f"{YEAR}-05-01", "D", "TQ3080")]
    sq = hd.hectad_squares(make_db(tmp_path, rows), hd.THIS_YEAR)
    assert sq == {"SP52": {"count": 120}, "TQ38": {"count": 1}}
    assert not hasattr(hd, "CLASSES") and not hasattr(hd, "record_class")


def test_every_square_one_colour_and_one_legend_swatch(qapp, tmp_path, sync_jobs):
    from PySide6.QtWidgets import QLabel
    from src.views.home.home_map_card import HomeMapCard, recorded_colour
    rows = [("Personal", "A a", "TA", f"{YEAR}-05-01", "D", "SP5820")] * 120 \
        + [("Personal", "B b", "TB", f"{YEAR}-05-01", "D", "TQ3080")] \
        + [("Personal", "B b", "TB", f"{YEAR}-05-01", "D", "SU1020")] * 12
    card = HomeMapCard()
    card.set_database(make_db(tmp_path, rows))
    card.reload()
    assert {v["fill"] for v in card._squares.values()} == {recorded_colour()} and len(card._squares) == 3
    legend = [lab.text() for lab in card.findChildren(QLabel) if lab.text() in ("Recorded", "1–9", "10–99", "100+ records")]
    assert legend == ["Recorded"]


# ------------------------------------------------------------------ the map: the Show list
def _combo(card):
    c = card.mode_combo
    return [("|" if c.itemText(i) == "" else c.itemData(i)) for i in range(c.count())]


def test_show_list_years_from_the_data_newest_first(qapp, tmp_path, sync_jobs):
    from src.views.home import home_data as hd
    from src.views.home.home_map_card import HomeMapCard
    rows = [("Personal", "A a", "TA", f"{YEAR}-05-01", "D", "SP5820"),
            ("Personal", "A a", "TA", f"{YEAR - 3}-05-01", "D", "SP5820"),
            ("Personal", "A a", "TA", f"{YEAR - 1}-05-01", "D", "SU1020"),
            ("Commercial", "A a", "TA", f"{YEAR - 2}-05-01", "D", "SP5820")]    # Commercial only
    db = make_db(tmp_path, rows)
    assert hd.map_years(db) == [YEAR, YEAR - 1, YEAR - 2, YEAR - 3]     # as the map: both kinds
    card = HomeMapCard()
    assert _combo(card) == ["year", "all", "species"]            # before the data is read
    card.set_database(db)
    card.reload()
    assert _combo(card) == ["year", "all", "species", "|", f"y:{YEAR - 1}", f"y:{YEAR - 2}",
                            f"y:{YEAR - 3}"]
    assert [card.mode_combo.itemText(i) for i in range(3)] == ["This year", "All years", "Selected species"]
    card.mode_combo.setCurrentIndex(card.mode_combo.findData(f"y:{YEAR - 3}"))     # reloads
    assert card.count_label.text() == f"1 ten-km square in {YEAR - 3}"
    card.mode_combo.setCurrentIndex(card.mode_combo.findData(hd.ALL_YEARS))
    assert card.count_label.text() == "2 ten-km squares in all years"
    card.mode_combo.setCurrentIndex(0)
    assert card.count_label.text() == f"1 ten-km square in {YEAR}"
    card.set_species("TA", "Aus bus")
    card.mode_combo.setCurrentIndex(card.mode_combo.findData(hd.SELECTED))
    assert card.count_label.text().endswith("for Aus bus")


def test_show_list_remembered_year_that_is_gone_falls_back_to_this_year(qapp, tmp_path, sync_jobs):
    from src.views.home.home_map_card import HomeMapCard
    has = make_db(tmp_path, [("Personal", "A a", "TA", f"{YEAR - 3}-05-01", "D", "SP5820"),
                             ("Personal", "A a", "TA", f"{YEAR}-05-01", "D", "SP5820")], "a.db")
    gone = make_db(tmp_path, [("Personal", "A a", "TA", f"{YEAR}-05-01", "D", "SP5820")], "b.db")
    card = HomeMapCard()
    card.set_database(has)
    card.reload()
    card.mode_combo.setCurrentIndex(card.mode_combo.findData(f"y:{YEAR - 3}"))
    assert card.choice() == f"y:{YEAR - 3}"
    card.set_database(gone)
    card.reload()
    assert card.choice() == "year" and _combo(card) == ["year", "all", "species"]
    assert card.count_label.text() == f"1 ten-km square in {YEAR}"


# ------------------------------------------------------------------ the Year list
TODAY = date(2026, 5, 15)


def _year_db(tmp_path):
    P, C = "Personal", "Commercial"
    rows = [(P, "A", "TA", "2026-01-10", "D", "SP5820"), (P, "B", "TB", "2026-01-20", "D", "SP5820"),
            (P, "A", "TA", "2026-03-03", "D", "SP5820"), (P, "C", "TC", "2026-03-05", "D", "SP5820"),
            (P, "D", "TD", "2026-03-07", "D", "SP5820"), (P, "I", "TI", "2026-03-09", "D", "SP5820"),
            (P, "E", "TE", "2026-04-01", "O", "SP5820"),          # a month date: placed in April
            (P, "F", "TF", "2026-01-01", "Y", "SP5820"),          # year only: in no month
            (P, "H", "TH", "2026-02-01", "DD", "SP5820"),         # a day range: in no month
            (P, "J", "TJ", "2026-08-02", "D", "SP5820"),          # after "today"
            (C, "G", "TG", "2026-02-02", "D", "SP5820"),          # Commercial: not on the list
            (P, "A", "TA", "2025-02-01", "D", "SP5820"), (P, "B", "TB", "2025-06-10", "D", "SP5820"),
            (P, "C", "TC", "2025-07-01", "D", "SP5820")]
    return make_db(tmp_path, rows)


def test_year_list_monthly_cumulative_values(tmp_path):
    from src.views.home import home_data as hd
    d = hd.year_list(_year_db(tmp_path), today=TODAY)
    # Jan A,B (2); Feb -; Mar C,D,I (5); Apr E (6); May -; plus F, H (no month) and J (after
    # today) in the last point drawn: 6 + 3 = 9; nothing after May
    assert d["this"] == [2, 2, 5, 6, 9] + [None] * 7
    assert d["total"] == 9 and d["unplaced"] == 2
    assert d["best"] == (3, 3)
    assert d["last"] == [0, 1, 1, 1, 1, 2, 3, 3, 3, 3, 3, 3]
    assert d["last_by_date"] == 1                       # by 15 May last year: A only


def test_year_list_empty_and_no_best_month(tmp_path):
    from src.views.home import home_data as hd
    d = hd.year_list(make_db(tmp_path, []), today=TODAY)
    assert d["this"][:5] == [0] * 5 and d["total"] == 0 and d["best"] is None and d["last_by_date"] == 0


def test_year_list_last_point_equals_the_personal_quick_stats_card(tmp_path, qapp, monkeypatch):
    """Same database, same switches: the chart's final value is the card's This Year Species."""
    import shared.species_counting as sc
    from src.models.database import get_database
    from src.repositories import ObservationRepository
    from src.views.home import home_data as hd
    from src.views.home.observation_stats_card import ObservationStatsCard
    P = "Personal"
    rows = [(P, "Aus aa", "TA", f"{YEAR}-01-10", "D", "SP5820"), (P, "Bus bb", "TB", f"{YEAR}-01-01", "Y", "SP5820"),
            (P, "Cus", "TC", f"{YEAR}-12-30", "D", "SP5820"), (P, "Aus aa", "TA", f"{YEAR}-01-12", "D", "SP5820"),
            ("Commercial", "Gus gg", "TG", f"{YEAR}-01-12", "D", "SP5820"),
            (P, "Old oo", "TO", f"{YEAR - 1}-01-12", "D", "SP5820")]
    path = make_db(tmp_path, rows)
    c = sqlite3.connect(path)
    c.execute("UPDATE observations SET taxon_rank = 'Genus' WHERE species_name = 'Cus'")
    c.commit()
    c.close()
    expected = {frozenset(): 3, frozenset({"genus"}): 2}      # A, B, C / A, B (the genus is left out)
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(path)
    try:
        for kinds in (frozenset(), frozenset({"genus"})):
            monkeypatch.setattr(sc, "excluded_kinds", lambda source, k=kinds: k)
            card = ObservationStatsCard("Personal")
            card.update_stats(ObservationRepository().get_quick_stats(record_type="Personal"))
            d = hd.year_list(path)
            shown = d["this"][date.today().month - 1]
            assert shown == d["total"] == int(card.value("this_year_species")) == expected[kinds]
    finally:
        db._main_db_path, db._uksi_db_path = old


def test_year_list_card_shows_the_figures_and_the_year_only_note(qapp):
    from src.views.home.year_list_card import YearListCard
    card = YearListCard()
    card.show_data({"year": 2026, "this": [2, 2, 5, 6, 9] + [None] * 7, "last": [0] * 12, "total": 9,
                    "last_by_date": 1, "best": (3, 3), "unplaced": 2, "unplaced_last": 0})
    assert card.this_value.text() == "9" and card.last_value.text() == "1"
    assert card.best_value.text() == "Mar (+3)"
    assert not card.note.isHidden() and card.note.text().startswith("2 species dated by year only")
    assert card.chart.values()[0][:5] == [2, 2, 5, 6, 9]
    card.show_data(None)
    assert card.note.isHidden()


# ------------------------------------------------------------------ the species card
def test_species_card_height_is_the_same_empty_and_filled(qapp):
    from src.views.home.species_info import SpeciesInfoPanel
    card = SpeciesInfoPanel()
    card.resize(560, 400)
    card.show()
    qapp.processEvents()
    empty = (card.height(), card.sizeHint().height(), card.body.height())
    card.set_species({"scientific_name": "Rutpela maculata", "common_name": "Harlequin Longhorn",
                      "family": "Cerambycidae", "tvk": "NBNSYS0000007359", "record_count": 12,
                      "in_collection": True, "specimen_count": 3,
                      "first_date": "2020-05-01", "last_date": "2026-06-02"})
    qapp.processEvents()
    filled = (card.height(), card.sizeHint().height(), card.body.height())
    card.set_species({"scientific_name": "Aus bus"})              # no common name, no records
    qapp.processEvents()
    sparse = (card.height(), card.sizeHint().height(), card.body.height())
    card.clear()
    qapp.processEvents()
    assert empty == filled == sparse == (card.height(), card.sizeHint().height(), card.body.height())
    # the filled details fit inside the fixed body
    card.set_species({"scientific_name": "Rutpela maculata", "common_name": "Harlequin Longhorn",
                      "family": "Cerambycidae", "record_count": 12, "in_collection": True,
                      "specimen_count": 3, "first_date": "2020-05-01", "last_date": "2026-06-02"})
    qapp.processEvents()
    assert card.content.layout().sizeHint().height() <= card.body.height()


def test_home_cards_below_do_not_move_when_a_species_is_picked(qapp):
    from src.views.home.home_tab import HomeTab
    h = HomeTab()
    h.resize(1366, 768)
    h.show()
    qapp.processEvents()
    ys = (h.recent_panel.geometry().top(), h.year_list_card.geometry().top())
    h.species_info.set_species({"scientific_name": "Rutpela maculata", "common_name": "Harlequin Longhorn",
                                "family": "Cerambycidae", "record_count": 12})
    qapp.processEvents()
    assert (h.recent_panel.geometry().top(), h.year_list_card.geometry().top()) == ys
    assert not hasattr(h, "notable_card")
