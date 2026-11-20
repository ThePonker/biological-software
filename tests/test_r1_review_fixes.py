"""Round 1 review fixes: unreadable accounts reach the report and the dialogs; own-account
read failures are visible. Purpose-made databases only."""
import sqlite3
from types import SimpleNamespace

import pytest
from _round_a_fixture import NAMES, T_RARE, add_committed, add_job, build
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from shared import species_accounts as sa
from Examen import examen_data as ed
from Examen import missing_profiles_dialog as mpd
from Examen import site_analysis_view as sav
from Examen import workbook_export as we
from Examen.report_model import build_report

PROFILES = ("CREATE TABLE species_profiles (id INTEGER PRIMARY KEY, species_tvk TEXT, "
            "species_name TEXT, common_name TEXT, profile_text TEXT, created_at TEXT, "
            "updated_at TEXT)")


def locked(*a, **k):
    raise sqlite3.OperationalError("database is locked")


@pytest.fixture
def world(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    build(tmp_path, monkeypatch)
    add_committed(tmp_path)
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    c.execute(PROFILES)
    c.commit()
    c.close()
    c = sqlite3.connect(str(tmp_path / "codex.db"))     # a published review account for T_RARE
    c.execute("INSERT INTO species_profiles VALUES (?, 'Review text.', 'Lane, 2020')", (T_RARE,))
    c.commit()
    c.close()
    return tmp_path


def _detail():
    return ed.load_project_detail("Notts Park", "Acme", survey_year="2026")


# -- item 4: your own account ----------------------------------------------------------------------
def test_own_account_read_error_is_recorded(tmp_path):
    acc = sa.get_species_accounts("T1", None, codex_db=str(tmp_path / "c.db"),
                                  observatum_db=str(tmp_path / "missing.db"))
    assert acc.own_read_error and acc.own is None


def test_own_account_without_a_profiles_table_is_just_no_account(tmp_path):
    db = tmp_path / "o.db"
    sqlite3.connect(db).close()
    acc = sa.get_species_accounts("T1", None, codex_db=str(tmp_path / "c.db"), observatum_db=str(db))
    assert acc.own_read_error is None and acc.own is None


def test_workbook_does_not_fall_back_to_a_review_when_yours_is_unreadable(world, monkeypatch):
    out = we._profiles({T_RARE}, [])
    assert "Review text." in out[T_RARE][0] or "Lane" in out[T_RARE][0]     # normal: review used
    monkeypatch.setattr(sa, "_own_account", locked)
    problems = []
    assert we._profiles({T_RARE}, problems) == {}
    assert problems == [(T_RARE, "your account could not be read")]


def test_missing_profiles_dialog_warns_and_does_not_list_unreadable(world, monkeypatch):
    detail = ed.load_entry_job_detail(add_job(world))
    monkeypatch.setattr(sa, "_own_account", locked)
    dlg = mpd.MissingProfilesDialog(detail)
    assert dlg.table.rowCount() == 0
    text = dlg.header.text()
    assert "could not be read" in text and NAMES[T_RARE] in text
    assert "have no account of yours" not in text.split("\n")[0]


def test_missing_profiles_dialog_normal_when_readable(world):
    detail = ed.load_entry_job_detail(add_job(world))
    dlg = mpd.MissingProfilesDialog(detail)
    assert "could not be read" not in dlg.header.text() and dlg.table.rowCount() > 0


# -- item 3: the report carries the warning --------------------------------------------------------
def test_build_report_carries_the_warning(world, monkeypatch):
    d = _detail()
    assert build_report(d.analysis, d, None)["warnings"] == []
    monkeypatch.setattr(sa, "_review_accounts", locked)
    monkeypatch.setattr(sa, "_own_account", lambda *a: (None, None))
    rep = build_report(d.analysis, d, None)
    assert rep["warnings"] and "database is locked" in rep["warnings"][0]


def _view(path, monkeypatch, answer, broken=True):
    d = _detail()
    if broken:
        monkeypatch.setattr(sa, "_review_accounts", locked)
        monkeypatch.setattr(sa, "_own_account", lambda *a: (None, None))
    fake = SimpleNamespace(_current_result=d.analysis, _current_detail=d, _current_project=None,
                           _current_site_name="Notts", _jurisdiction="England", _pooled=lambda: False)
    fake._confirm_report_warnings = lambda w: sav.SiteAnalysisView._confirm_report_warnings(fake, w)
    asked, told = [], []
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(path), "")))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: asked.append(a[2]) or answer)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: told.append(a[1]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: told.append(a[2]))
    return fake, asked, told


CASES = [("_on_export_pdf", "reportlab", ".pdf"), ("_on_export_word", "docx", ".docx"),
         ("_on_export_pack", "docx", ".docx")]


@pytest.mark.parametrize("method,module,ext", CASES)
def test_declining_the_account_warning_writes_nothing(world, monkeypatch, tmp_path, method, module, ext):
    pytest.importorskip(module)
    out = tmp_path / f"r{ext}"
    fake, asked, told = _view(out, monkeypatch, QMessageBox.StandardButton.No)
    getattr(sav.SiteAnalysisView, method)(fake)
    assert asked and "Some species accounts could not be read" in asked[0]
    assert "database is locked" in asked[0] and "Write the report anyway?" in asked[0]
    assert not out.exists() and not told


@pytest.mark.parametrize("method,module,ext", CASES)
def test_accepting_the_account_warning_writes_the_report(world, monkeypatch, tmp_path, method, module, ext):
    pytest.importorskip(module)
    out = tmp_path / f"r{ext}"
    fake, asked, told = _view(out, monkeypatch, QMessageBox.StandardButton.Yes)
    getattr(sav.SiteAnalysisView, method)(fake)
    assert asked and out.is_file() and out.stat().st_size > 0 and told


@pytest.mark.parametrize("method,module,ext", CASES)
def test_no_question_when_nothing_went_wrong(world, monkeypatch, tmp_path, method, module, ext):
    pytest.importorskip(module)
    out = tmp_path / f"r{ext}"
    fake, asked, told = _view(out, monkeypatch, QMessageBox.StandardButton.No, broken=False)
    getattr(sav.SiteAnalysisView, method)(fake)
    assert not asked and out.is_file()
