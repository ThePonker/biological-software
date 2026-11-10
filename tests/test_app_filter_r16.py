"""Round 16 C2: one application event filter for tick_style, calendar_style, opaque_popups and
dialog_geometry, and each behaviour still happens."""
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QCalendarWidget, QCheckBox, QComboBox, QDialog

from shared import app_filter, calendar_style, dialog_geometry, opaque_popups, tick_style

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


GREEN = dict(fill="#4a7c59", mark="#ffffff", border="#9ca3af", background="#ffffff")


class _Sized(QDialog):
    pass


def test_one_filter_and_each_behaviour(qapp, monkeypatch):
    installs = []
    real = QApplication.installEventFilter
    monkeypatch.setattr(QApplication, "installEventFilter",
                        lambda self, f: (installs.append(f), real(self, f))[1])
    monkeypatch.setattr(app_filter, "_filter", None)
    monkeypatch.setattr(tick_style, "_installed", None)
    monkeypatch.setattr(calendar_style, "_installed", None)
    monkeypatch.setattr(opaque_popups, "_installed", None)
    monkeypatch.setattr(dialog_geometry, "_installed", [])
    try:
        tick_style.install(qapp, lambda: GREEN)
        calendar_style.install(qapp, lambda: dict(
            surface="#fff", surface_alt="#eee", text_primary="#111", text_secondary="#444",
            text_muted="#888", border="#ccc", hover="#ddd", accent="#4a7c59",
            accent_text="#fff", weekend="#d97706", today_bg="#e6f0e9"))
        opaque_popups.install(qapp, lambda: ("#fafafa", "#111111"))
        dialog_geometry.install(qapp)
        assert len(installs) == 1                       # one filter on the app for all four
        assert tick_style.install(qapp) is tick_style._installed

        box = QCheckBox("x")
        box.show()
        assert tick_style.is_styled(box)

        cal = QCalendarWidget()
        cal.show()
        assert calendar_style.is_styled(cal)

        combo = QComboBox()
        combo.setStyleSheet("background: transparent;")
        combo.addItems(["a", "b"])
        combo.show()
        combo.showPopup()
        qapp.processEvents()
        assert not opaque_popups.is_see_through(combo.view())
        combo.hidePopup()

        d = _Sized()
        dialog_geometry.save(d)
        d.show()
        assert d.property(dialog_geometry._FLAG)
        dialog_geometry._settings().remove(dialog_geometry.key_for(d))
        for w in (box, cal, combo, d):
            w.close()
            w.deleteLater()
    finally:
        qapp.removeEventFilter(app_filter._filter)       # the extra filter this test installed
        app_filter.unregister(qapp, "tick_style")
        app_filter.unregister(qapp, "calendar_style")
        app_filter.unregister(qapp, "opaque_popups")
        app_filter.unregister(qapp, "dialog_geometry")


def test_other_events_skip_handlers(qapp):
    seen = []
    f = app_filter.AppFilter(qapp)
    f.register("t", lambda o, e: seen.append(e.type()), (QEvent.Type.Show,))
    f.register("bad", lambda o, e: 1 / 0, (QEvent.Type.Show,))     # must not stop the others
    assert f.eventFilter(None, QEvent(QEvent.Type.Paint)) is False and not seen
    assert f.eventFilter(None, QEvent(QEvent.Type.Show)) is False and seen == [QEvent.Type.Show]
    f.unregister("t")
    f.unregister("bad")
    f.eventFilter(None, QEvent(QEvent.Type.Show))
    assert len(seen) == 1
