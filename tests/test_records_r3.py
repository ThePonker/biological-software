"""Round 9 records items, 11 Oct 2026.

R9-1  Stats > Species lookup: a taxon picked from the list is never left out of its own
      counts. On the 10 Oct data copy, with the Scheme "Aggregate" switch on, Leiopus
      linnei/nebulosus showed 0 Scheme records; now 1,933 (and 3 observations, not 0).
R9-3  "Open in iRecord" in the record detail dialogs and the Mapping square list, for any
      record holding an iRecord ID (shared/irecord_links.py is the one link pattern).
"""
import os
import sqlite3
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402
import shared.species_counting as sc  # noqa: E402
from shared.irecord_links import (IRECORD_URL, irecord_id_of, irecord_ids,  # noqa: E402
                                  irecord_url, record_irecord_url)

needs_data = pytest.mark.skipif(not os.path.exists(paths.OBSERVATUM_DB),
                                reason="no data/observatum.db")
AGG_TVK = "NHMSYS0021478843"            # Leiopus linnei/nebulosus (Species aggregate)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("records_r3")
    QSettings().clear()
    old_default = sc._default_db
    sc.invalidate()
    yield QSettings()
    QSettings().clear()
    sc._default_db = old_default
    sc.invalidate()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


# ------------------------------------------------------------------ R9-1

def test_kinds_for_taxon(settings):
    sc.set_excluded("recording_scheme", ["agg", "genus", "sl"])
    agg = sc.kinds_for_taxon("recording_scheme", "Leiopus linnei/nebulosus", "Species aggregate")
    assert agg == {"genus", "sl"}                            # its own kind kept, others still out
    assert sc.kinds_for_taxon("recording_scheme", "Leiopus linnei/nebulosus") == {"genus", "sl"}
    assert sc.kinds_for_taxon("recording_scheme", "Xanthogramma pedissequum",
                              "Species sensu lato") == {"genus", "agg"}
    assert sc.kinds_for_taxon("recording_scheme", "Leiopus nebulosus", "Species") == \
        {"agg", "genus", "sl"}
    # the tabs' text rule reads the slash pair too since decision D4 (test_counting_r3)
    assert sc.kinds_for_search("recording_scheme", "Leiopus linnei/nebulosus") == {"genus"}


def _lookup_db(tmp_path):
    conn = sqlite3.connect(tmp_path / "o.db")
    for t in ("observations", "specimens", "recording_scheme"):
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, species_tvk TEXT, "
                     "species_name TEXT, taxon_rank TEXT, common_name TEXT, record_type TEXT, "
                     "date TEXT, date_type TEXT)")
    rows = [(AGG_TVK, "Leiopus linnei/nebulosus", "Species aggregate")] * 4 + [
        (AGG_TVK, "Leiopus linnei/nebulosus agg.", "Species")] * 2
    for t in ("observations", "recording_scheme"):
        conn.executemany(f"INSERT INTO {t} (species_tvk, species_name, taxon_rank, record_type, "
                         "date) VALUES (?, ?, ?, 'Personal', '2024-05-01')", rows)
    conn.commit()
    conn.close()
    return tmp_path / "o.db"


def test_species_lookup_shows_picked_aggregate(settings, tmp_path):
    from src.views.stats.species_dashboard import SpeciesDashboard
    path = _lookup_db(tmp_path)
    conn = sqlite3.connect(path)

    class Db:
        main_db_path = str(path)

        def execute_main(self, sql, params=()):
            return conn.execute(sql, params).fetchall()

    sc.set_excluded("observations", ["agg"])
    sc.set_excluded("recording_scheme", ["agg"])
    r = SimpleNamespace(scientific_name="Leiopus linnei/nebulosus", tvk=AGG_TVK, common_name=None,
                        family="Cerambycidae", order_name="Coleoptera", old_name=None,
                        match_type="exact", rank="Species aggregate")
    before = SpeciesDashboard()
    before._db = Db()
    # by text alone it was 0 (the R9-1 fault); the text rule reads the slash pair since D4
    assert before._count("recording_scheme", r.scientific_name) == 6
    d = SpeciesDashboard()
    d._db = Db()
    d._search_results = [r]
    d._on_completer_activated(d._display(r))
    sp = d._selected_species
    assert (sp["schemeRecords"], sp["observationRecords"], sp["personalRecords"]) == (6, 6, 6)
    assert sum(sp["phenology"]) == 12
    assert "Aggregate (agg.) records are counted here" in d._counting_note.text()
    conn.close()


@needs_data
def test_species_lookup_leiopus_on_copy(settings):
    from src.views.stats.species_dashboard import SpeciesDashboard
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

    class Db:
        main_db_path = str(paths.OBSERVATUM_DB)

        def execute_main(self, sql, params=()):
            return conn.execute(sql, params).fetchall()

    sc.set_excluded("recording_scheme", ["agg"])
    from shared.scheme_duplicates import live_sql   # each record once: marked NBN copies out
    want = conn.execute("SELECT COUNT(*) FROM recording_scheme WHERE species_tvk=?" + live_sql(conn),
                        (AGG_TVK,)).fetchone()[0]
    d = SpeciesDashboard()
    d._db = Db()
    d._search_results = [SimpleNamespace(
        scientific_name="Leiopus linnei/nebulosus", tvk=AGG_TVK, common_name=None,
        family="Cerambycidae", order_name="Coleoptera", old_name=None, match_type="exact",
        rank="Species aggregate")]
    d._on_completer_activated(d._display(d._search_results[0]))
    assert d._selected_species["schemeRecords"] == want > 1800   # 1,933; 1,832 with copies marked
    conn.close()


# ------------------------------------------------------------------ R9-3

def test_irecord_links():
    assert IRECORD_URL == "https://irecord.org.uk/record-details?occurrence_id={id}"
    assert irecord_url(4944675).endswith("occurrence_id=4944675")
    assert irecord_url(" 127178 ").endswith("=127178")
    for bad in (None, "", 0, "0", -3, "abc", True):
        assert irecord_url(bad) is None and irecord_id_of(bad) is None
    assert record_irecord_url({"irecord_id": 5}) and record_irecord_url({}) is None
    from src.services.cleaning_report import IRECORD_URL as CR_URL, irecord_url as cr_url
    assert CR_URL is IRECORD_URL and cr_url is irecord_url              # one pattern


def test_irecord_ids_lookup(tmp_path):
    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER)")
    conn.executemany("INSERT INTO observations VALUES (?, ?)", [(1, 111), (2, None), (3, 0)])
    assert irecord_ids(conn, "observations", [1, 2, 3, 9]) == {1: 111}
    assert irecord_ids(conn, "specimens", [1]) == {}


def test_irecord_button(qapp):
    from src.views.components.irecord_button import IRecordButton, irecord_button_for
    opened = []
    b = IRecordButton(4944675)
    b.open_url = lambda u: opened.append(u.toString())
    assert b.isEnabled() and b.text() == "Open in iRecord"
    b.click()
    assert opened == [IRECORD_URL.format(id=4944675)]
    b.set_irecord_id(None)
    assert not b.isEnabled() and "no iRecord ID" in b.toolTip()
    b.click()
    assert len(opened) == 1
    assert irecord_button_for({"irecord_id": None}) is None
    assert irecord_button_for({"irecord_id": 7}) is not None


@pytest.mark.parametrize("which", ["observation", "specimen", "scheme"])
def test_detail_dialogs_show_button_only_with_id(qapp, which):
    from src.views.dialogs import RecordDetailDialog, SchemeRecordDetailDialog

    def make(rec):
        if which == "scheme":
            return SchemeRecordDetailDialog(rec)
        return RecordDetailDialog(rec, record_type=which)

    base = {"species_name": "Rutpela maculata", "date": "2024-06-01", "grid_ref": "SP4527"}
    with_id = make({**base, "irecord_id": 24909235, "source": "iRecord | iRecord App"})
    assert with_id.irecord_btn is not None and with_id.irecord_btn.isEnabled()
    assert with_id.irecord_btn.url().endswith("occurrence_id=24909235")
    without = make({**base, "irecord_id": None})
    assert without.irecord_btn is None


@needs_data
def test_square_dialog_irecord_button(qapp, settings):
    from src.views.mapping.square_records_dialog import SquareRecordsDialog
    sc.set_default_db(paths.OBSERVATUM_DB)
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    has = conn.execute("SELECT id, irecord_id FROM observations WHERE irecord_id > 0 "
                       "ORDER BY id LIMIT 1").fetchone()
    no = conn.execute("SELECT id FROM observations WHERE irecord_id IS NULL "
                      "ORDER BY id LIMIT 1").fetchone()
    conn.close()
    recs = [{"table": "observations", "id": has[0], "species_name": "A", "date": "2024-01-02"},
            {"table": "observations", "id": no[0], "species_name": "B", "date": "2024-01-01"},
            {"table": "specimens", "id": 1, "species_name": "C", "date": "2023-01-01"}]
    d = SquareRecordsDialog("SP42", "Hectad", recs)
    opened = []
    d.irecord_btn.open_url = lambda u: opened.append(u.toString())
    assert not d.irecord_btn.isHidden() and not d.irecord_btn.isEnabled()   # nothing selected
    row = {d.table.item(i, 1).text(): i for i in range(d.table.rowCount())}
    d.table.selectRow(row["B"])
    assert not d.irecord_btn.isEnabled()
    d.table.selectRow(row["A"])
    assert d.irecord_btn.isEnabled()
    d.irecord_btn.click()
    assert opened == [IRECORD_URL.format(id=has[1])]
    d.table.sortItems(1, d.table.horizontalHeader().sortIndicatorOrder())   # sorting keeps keys
    d.table.selectRow({d.table.item(i, 1).text(): i for i in range(3)}["C"])
    assert not d.irecord_btn.isEnabled()
    none = SquareRecordsDialog("SP42", "Hectad", recs[1:])
    assert none.irecord_btn.isHidden()


# ------------------------------------------------------------------ F43

needs_uksi = pytest.mark.skipif(not os.path.exists(paths.UKSI_DB), reason="no data/uksi.db")


def _f43_module():
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "_oneoff", "fix_melanotus_tvk_20261011.py")
    spec = importlib.util.spec_from_file_location("fix_melanotus_tvk_20261011", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@needs_uksi
def test_f43_script(tmp_path, capsys):
    f = _f43_module()
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, "
              "species_tvk TEXT, kingdom TEXT, order_name TEXT, family TEXT, superfamily TEXT, "
              "taxon_group TEXT, taxon_rank TEXT, taxonomic_sort_key INTEGER, irecord_id INTEGER, "
              "source TEXT, import_notes TEXT, updated_at TEXT)")
    bad = (f.BAD_TVK, "Fungi", "Agaricales", "Strophariaceae", None, "fungus", "Genus", None)
    c.executemany("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (1, "Melanotus", *bad, None, None, None, None),
        (2, "Melanotus", *bad, 555, "iRecord | iRecord general data", "old note", None),
        (3, "Psilocybe x", *bad, None, None, None, None),          # not named Melanotus: left
    ])
    c.commit()
    c.close()
    assert f.main(["--db", str(db)]) == 0                           # dry run
    out = capsys.readouterr().out
    assert "2 records to move" in out and "Nothing has been changed" in out
    assert "id 2: iRecord ID 555, taxon_group 'fungus' -> 'insect - beetle (Coleoptera)'" in out
    assert sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM observations WHERE species_tvk=?", (f.BAD_TVK,)).fetchone()[0] == 3
    assert f.main(["--db", str(db), "--apply", "--backup-dir", str(tmp_path / "bk")]) == 0
    rows = {r[0]: r for r in sqlite3.connect(db).execute(
        "SELECT id, species_tvk, kingdom, order_name, family, taxon_group, superfamily, "
        "import_notes FROM observations")}
    for i in (1, 2):
        assert rows[i][1:6] == (f.GOOD_TVK, "Animalia", "Coleoptera", "Elateridae",
                                "insect - beetle (Coleoptera)")
        assert rows[i][6] is None                                    # blank left for backfill
        assert "(F43)" in rows[i][7]
    assert rows[2][7].startswith("old note [TVK corrected")
    assert rows[3][1] == f.BAD_TVK
    assert len(os.listdir(tmp_path / "bk")) == 1
