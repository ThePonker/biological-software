"""Examen toolbar: one Export menu in place of six buttons; no 'Data Entry job...' button."""
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMenu, QPushButton  # noqa: E402

from _round_a_fixture import build  # noqa: E402

LABELS = ["Report pack…", "Workbook…", "Appendix…", "Projects list (CSV)…", None,
          "Assessment report (Word)…", "Assessment report (PDF)…"]


@pytest.fixture
def view(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    build(tmp_path, monkeypatch)
    from Examen import examen_data as ed
    from Examen import site_analysis_view as sav
    called = []
    for name in ("_on_export_pack", "_on_export_workbook", "_on_export_appendix", "_export_csv",
                 "_on_export_word", "_on_export_pdf"):
        monkeypatch.setattr(sav.SiteAnalysisView, name, lambda self, *a, _n=name: called.append(_n))
    v = sav.SiteAnalysisView(ed.analysis_service())
    v.called = called
    return v


def _texts(view):
    return [b.text() for b in view.findChildren(QPushButton)]


def test_one_export_menu_in_order(view):
    assert view.export_btn.text().startswith("Export")
    menu = view.export_btn.menu()
    assert isinstance(menu, QMenu)
    assert [None if a.isSeparator() else a.text() for a in menu.actions()] == LABELS


def test_old_export_buttons_and_data_entry_button_are_gone(view):
    texts = _texts(view)
    for gone in ("Export Appendix", "Export Workbook", "Export PDF", "Export Word",
                 "Export Report pack", "Export CSV", "Data Entry job…"):
        assert gone not in texts
    assert not any(t.startswith("Data Entry") for t in texts)
    for kept in ("Import List...", "Refresh", "Benchmark…", "Status marks…"):
        assert kept in texts
    assert hasattr(view, "_on_entry_job")              # the handler stays


def test_enabled_rules_and_handlers(view):
    menu = view.export_btn.menu()
    acts = {a.text(): a for a in menu.actions() if not a.isSeparator()}
    needs = [t for t in acts if "CSV" not in t]
    assert not any(acts[t].isEnabled() for t in needs)          # nothing analysed yet
    assert acts["Projects list (CSV)…"].isEnabled()           # as the old CSV button was
    view._set_exports_enabled(True)
    assert all(acts[t].isEnabled() for t in needs)
    view._clear_detail("nothing")
    assert not any(acts[t].isEnabled() for t in needs) and acts["Projects list (CSV)…"].isEnabled()
    view._set_exports_enabled(True)
    for a in acts.values():
        a.trigger()
    assert view.called == ["_on_export_pack", "_on_export_workbook", "_on_export_appendix",
                           "_export_csv", "_on_export_word", "_on_export_pdf"]
