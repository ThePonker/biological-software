"""R18 B3 / B4: the scheme import shows species lookups that failed (counted, named, logged), and
its confirmation page says scheme records cannot be removed."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pandas")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import species_lookup_harness as h  # noqa: E402

h.stub_webengine()

from PySide6.QtWidgets import QApplication  # noqa: E402

from test_import_fixes import FakeUKSIModel  # noqa: E402
from test_imports_20261010 import OK, _scheme  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _failing(monkeypatch, bad):
    """lookup_names for the scheme worker raising inside the lookup of the names in `bad`."""
    from shared import species_lookup as sl
    from src.views.dialogs.scheme_import_wizard import validation_worker as vw
    real = sl.lookup_names
    notes = []

    def fake(names, uksi, **kw):
        out = real(names, uksi, **kw)
        for n in names:
            if n in bad:
                out[n] = sl.LookupFailure(n, "error", "database is locked")
        return out
    monkeypatch.setattr(vw, "lookup_names", fake)
    monkeypatch.setattr(vw.crash_log, "note", lambda text, exc=None: notes.append(text))
    return notes


def test_failed_lookups_are_logged_and_listed_in_the_summary(app, monkeypatch):
    notes = _failing(monkeypatch, {"Carabus nemoralis"})
    rows = _scheme("GENERIC_CSV", [dict(OK), dict(OK, Species="Carabus nemoralis")])
    assert rows[0].status.name != "ERROR"                       # the name that did not fail: as before
    assert rows[1].status.name == "ERROR" and "database is locked" in rows[1].error_message
    assert len(notes) == 1 and "Carabus nemoralis" in notes[0] and "database is locked" in notes[0]

    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=FakeUKSIModel(), vc_service=None, db=None)
    w.validated_rows = rows
    w.imported_count = w.updated_count = w.error_count = 0
    w._update_summary()
    text = w.summary_stats.text()
    assert "Species lookups that failed: 1 (Carabus nemoralis)" in text
    w.deleteLater()


def test_nothing_failing_adds_no_line_and_no_log(app, monkeypatch):
    notes = _failing(monkeypatch, set())
    rows = _scheme("GENERIC_CSV", [dict(OK), dict(OK, Species="No such species")])
    assert notes == []
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=FakeUKSIModel(), vc_service=None, db=None)
    w.validated_rows = rows
    assert w._lookup_failure_lines() == []
    w.deleteLater()


def test_confirmation_page_says_scheme_records_cannot_be_removed(app):
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    assert w.no_delete_note.text().startswith("Scheme records cannot be removed in Observatum")
    assert w.stack.indexOf(w.no_delete_note.parentWidget()) >= 0
    w.deleteLater()
