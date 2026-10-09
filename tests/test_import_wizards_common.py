"""The pieces the three import wizards now share (C4, 9 Oct 2026): they still build offscreen,
and the shared table model / problem export behave as each wizard's own copy did."""
import csv
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import species_lookup_harness as h  # noqa: E402

h.stub_webengine()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_the_three_wizards_build(app):
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    from src.views.dialogs.specimen_import_wizard import SpecimenImportWizard
    from src.views.dialogs.import_common.mode_option_card import ModeOptionCard
    for cls, pages, cards in ((ObservationImportWizard, 7, 3), (SpecimenImportWizard, 5, 0),
                              (SchemeImportWizard, 7, 3)):
        kw = {} if cls is SpecimenImportWizard else {"db": None}
        w = cls(parent=None, uksi_model=None, vc_service=None, **kw)
        assert w.stack.count() == pages
        assert len(w.findChildren(ModeOptionCard)) == cards
        assert w.summary_title.text() and w.import_progress.maximum() == 100
        w.deleteLater()


def test_table_models_keep_their_own_columns(app):
    from src.views.dialogs.row_status import RowStatus
    from src.views.dialogs.scheme_import_wizard.validation_table_model import SchemeValidationTableModel
    from src.views.dialogs.scheme_import_wizard.validation_worker import SchemeImportRow
    from src.views.dialogs.specimen_import_wizard.validation_table_model import ValidationTableModel
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow

    spec = ValidationTableModel()
    r = ImportRow(row_number=5, raw_data={}, status=RowStatus.WARNING, species_name="Carabus nemoralis",
                  vc_number=23, warnings=["a", "b"])
    spec.set_data([r])
    ix = spec.index(0, 7)
    assert spec.columnCount() == 8 and spec.data(spec.index(0, 0)) == "[!]"
    assert spec.data(spec.index(0, 5)) == "VC23" and spec.data(ix) == "a; b"
    assert spec.data(ix, Qt.ToolTipRole) == "a; b" and spec.data(ix, Qt.ForegroundRole) is None
    assert spec.flags(spec.index(0, 3)) & Qt.ItemIsEditable and not spec.flags(spec.index(0, 2)) & Qt.ItemIsEditable
    assert spec.get_all_rows() == [r]

    sch = SchemeValidationTableModel()
    sch.pre_allocate(2)
    assert sch.data(sch.index(1, 0)) == "..." and sch.get_all_rows() == []
    s = SchemeImportRow(row_number=3, raw_data={}, status=RowStatus.ERROR, error_message="bad",
                        import_notes="note")
    sch.set_row(1, s)
    assert sch.data(sch.index(1, 6)) == "bad | note" and sch.data(sch.index(1, 0)) == "✗"
    assert sch.data(sch.index(1, 6), Qt.ForegroundRole) is not None
    assert sch.flags(sch.index(1, 2)) & Qt.ItemIsEditable and sch.get_all_rows() == [s]


def test_problem_export_writes_the_rows_as_read(app, tmp_path, monkeypatch):
    from src.views.dialogs.import_common import problem_export as pe
    from src.views.dialogs.row_status import RowStatus
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow
    out = tmp_path / "p.csv"
    asked = []
    monkeypatch.setattr(pe.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (asked.append(a[2]) or str(out), "")))
    monkeypatch.setattr(pe.QMessageBox, "information", staticmethod(lambda *a: None))
    monkeypatch.setattr(pe.QMessageBox, "critical", staticmethod(lambda *a: pytest.fail(a[2])))

    class W(pe.ProblemExportMixin):
        PROBLEMS_FILE_NAME = "specimen_import_problems.csv"
        columns = ["Species", "Date"]
        validated_rows = [
            ImportRow(2, {"Species": "Ok", "Date": "1/1/2020"}, status=RowStatus.VALID),
            ImportRow(3, {"Species": "Zzz", "Date": ""}, status=RowStatus.ERROR,
                      error_message="Species not found: Zzz")]
    W()._export_problems()
    assert asked == ["specimen_import_problems.csv"]
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert rows == [{"_Status": "error", "_Row": "3", "_Error": "Species not found: Zzz",
                     "Species": "Zzz", "Date": ""}]
