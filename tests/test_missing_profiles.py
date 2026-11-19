"""Examen's Missing profiles dialog: species with no account of yours, and the editor hand-off."""
import sqlite3

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from _round_a_fixture import NAMES, T_COMMON, T_RARE, T_SCARCE, T_VU, add_job, build  # noqa: E402

from Examen import examen_data as ed  # noqa: E402
from Examen import missing_profiles_dialog as mpd  # noqa: E402
from Examen import site_analysis_view as sav  # noqa: E402

PROFILES = ("CREATE TABLE species_profiles (id INTEGER PRIMARY KEY, species_tvk TEXT, "
            "species_name TEXT, common_name TEXT, profile_text TEXT, created_at TEXT, "
            "updated_at TEXT)")


def _write_account(folder, tvk):
    c = sqlite3.connect(str(folder / "observatum.db"))
    c.execute("INSERT INTO species_profiles (species_tvk, species_name, profile_text) "
              "VALUES (?,?,?)", (tvk, NAMES[tvk], "My account."))
    c.commit()
    c.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    build(tmp_path, monkeypatch)
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    c.execute(PROFILES)
    c.commit()
    c.close()
    _write_account(tmp_path, T_RARE)                  # an account for one Key Species
    return tmp_path


@pytest.fixture
def detail(world):
    return ed.load_entry_job_detail(add_job(world))


def _rows(dlg):
    return [dlg.table.item(i, 0).text() for i in range(dlg.table.rowCount())]


def test_lists_only_key_species_without_an_account(detail):
    dlg = mpd.MissingProfilesDialog(detail)
    assert _rows(dlg) == [NAMES[T_VU], NAMES[T_SCARCE]]          # Rare before Scarce; T_RARE has one
    assert [dlg.table.item(i, 3).text() for i in range(2)] == ["1", "1"]      # records
    assert dlg.table.item(0, 0).font().italic()


def test_show_all_adds_the_non_key_species(detail):
    dlg = mpd.MissingProfilesDialog(detail)
    dlg.show_all.setChecked(True)
    assert _rows(dlg) == [NAMES[T_VU], NAMES[T_SCARCE], NAMES[T_COMMON]]   # no plant, no T_RARE
    dlg.show_all.setChecked(False)
    assert len(_rows(dlg)) == 2


def test_header_line_counts(detail):
    dlg = mpd.MissingProfilesDialog(detail)
    assert dlg.header.text() == "2 of 3 Key Species have no account of yours."
    dlg.show_all.setChecked(True)
    assert dlg.header.text().startswith("2 of 3 Key Species have no account of yours.")
    assert "3 of 4 species in all" in dlg.header.text()


def test_review_account_column(detail, world):
    c = sqlite3.connect(str(world / "codex.db"))
    c.execute("DROP TABLE species_profiles")
    c.execute("CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT, "
              "review_id INTEGER)")
    c.execute("INSERT INTO species_profiles VALUES (?, 'Published text.', 'Lane, 2026', 0)", (T_VU,))
    c.commit()
    c.close()
    dlg = mpd.MissingProfilesDialog(detail)
    assert [dlg.table.item(i, 4).text() for i in range(2)] == ["yes", ""]


def test_saving_an_account_in_the_editor_drops_the_species(detail, world, monkeypatch):
    opened = []

    class FakeEditor:
        def __init__(self, data, parent=None):
            opened.append(data)

        def exec(self):
            _write_account(world, T_VU)

    monkeypatch.setattr(mpd, "editor_class", lambda: FakeEditor)
    monkeypatch.setattr(mpd, "point_observatum_database", lambda: None)
    dlg = mpd.MissingProfilesDialog(detail)
    dlg.table.cellDoubleClicked.emit(0, 0)
    assert opened == [{"tvk": T_VU, "scientific_name": NAMES[T_VU], "common_name": ""}]
    assert _rows(dlg) == [NAMES[T_SCARCE]]
    assert dlg.header.text() == "1 of 3 Key Species have no account of yours."
    dlg.table.selectRow(0)
    dlg.write_btn.click()                                   # the button does the same
    assert len(opened) == 2 and opened[1]["tvk"] == T_SCARCE


def test_button_disabled_until_a_survey_is_analysed(world):
    view = sav.SiteAnalysisView(ed.analysis_service())
    assert "Missing profiles…" in [b.text() for b in view.findChildren(sav.QPushButton)]
    assert not view.missing_btn.isEnabled()
    d = ed.load_entry_job_detail(add_job(world))
    view._current_detail = d
    view._current_project = ed.ProjectRecord(project_name="Notts Park", client="Acme")
    view._run_analysis([s.tvk for s in d.species_list], {}, "t", result=d.analysis)
    assert view.missing_btn.isEnabled()
    view._clear_detail("none")
    assert not view.missing_btn.isEnabled()


def test_editor_import_failure_shows_a_message(detail, monkeypatch):
    import builtins
    real = builtins.__import__

    def refuse(name, *a, **k):
        if name.startswith("src.views.home.species_profile_dialog"):
            raise ImportError("no Observatum")
        return real(name, *a, **k)
    with monkeypatch.context() as m:
        m.setattr(builtins, "__import__", refuse)
        assert mpd.editor_class() is None
    shown = []
    monkeypatch.setattr(mpd, "editor_class", lambda: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a: shown.append(a[2]))
    dlg = mpd.MissingProfilesDialog(detail)
    dlg.write_account(0)                                    # no exception
    assert len(shown) == 1 and "Observatum" in shown[0]
    assert len(_rows(dlg)) == 2


def test_database_pointed_only_where_unset(world, monkeypatch):
    import paths
    from src.models import database as obs_db
    monkeypatch.setattr(obs_db, "_db_manager", obs_db.DatabaseManager())
    mpd.point_observatum_database()
    db = obs_db.get_database()
    assert db.main_db_path == paths.OBSERVATUM_DB and db.uksi_db_path == paths.UKSI_DB
    db.set_main_path(str(world / "examen.db"))               # already set: left alone
    mpd.point_observatum_database()
    assert db.main_db_path.name == "examen.db"
