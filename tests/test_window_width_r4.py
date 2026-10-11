"""Main window minimum width (Round 4, 11 Oct 2026).

On Wil's PC the window could not be narrowed below ~1,730 px: the filter bars and
toolbars of Observation Data / Recording Scheme / Insect Collection, Home's four panels
(80 leader dots per figure, the Achievements card), the Contributed header line and the
Stats section buttons each held it wide. Now toolbars and filter bars scroll sideways in
an HScrollStrip, Home and the tabs built on first opening scroll as a page (PageScroll),
and the long labels wrap.

"wide" stands in for text that measures much wider than the Linux test fonts: every
letter spaced to 200 % (as tests/test_dataentry_r3.py). No assertion depends on how wide
a font measures; no database is opened (Data Entry and Mapping are stand-ins, the data
tabs are built but not initialised).
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

LIMIT = 1280


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def metrics_font(qapp, request):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    before = QFont(QApplication.font())
    if getattr(request, "param", "default") == "wide":
        f = QFont(before)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 200)
        QApplication.setFont(f)
    yield getattr(request, "param", "default")
    QApplication.setFont(before)


def _pump(qapp, n=4):
    for _ in range(n):
        qapp.processEvents()


@pytest.fixture
def window(qapp, monkeypatch, metrics_font):
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QWidget
    import DataEntry.embed as de_embed
    import src.views.main_window as mw
    import src.views.mapping as mapping_pkg
    from src.views.settings import SettingsTab

    class FakeDataEntry(QWidget):
        committed = Signal()

    class FakeMapping(QWidget):            # the real one projects every VC outline (slow)
        def __init__(self, *a, **k):
            super().__init__()
            self.setMinimumWidth(3000)      # far wider than any window

    monkeypatch.setattr(de_embed, "make_data_entry_tab", lambda **k: FakeDataEntry())
    monkeypatch.setattr(mapping_pkg, "MappingTab", FakeMapping)
    monkeypatch.setattr(mw.MainWindow, "_initialize_services", lambda self: None)
    monkeypatch.setattr(SettingsTab, "initialize", lambda self: None)
    # closing the real window backs up the databases: not from a test
    monkeypatch.setattr(mw.MainWindow, "closeEvent", lambda self, e: e.accept())
    w = mw.MainWindow()
    for name in ("stats_reports_tab", "mapping_tab", "settings_tab"):
        w.ensure_tab(name)
    w.resize(1600, 900)
    w.show()
    w.connect_tab_signal()
    _pump(qapp)
    yield w
    w.close()
    w.deleteLater()


@pytest.mark.parametrize("metrics_font", ["default", "wide"], indirect=True)
def test_every_tab_lets_the_window_narrow(window, qapp, metrics_font):
    w = window
    # the filter bars start hidden; Wil usually has them shown
    for bar in (w.observation_tab.filter_bar, w.recording_scheme_tab.filter_bar,
                w.insect_collection_tab.filters):
        bar.setVisible(True)
    _pump(qapp)
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i)
        _pump(qapp, 2)
        page = w.tabs.widget(i)
        name = w.tabs.tabText(i)
        assert page.minimumSizeHint().width() <= LIMIT, (metrics_font, name)
        assert w.minimumSizeHint().width() <= LIMIT, (metrics_font, name)
    # the toolbars and section buttons are still on screen (not lost in their strips)
    for tab, bar in ((w.observation_tab, w.observation_tab.toolbar),
                     (w.recording_scheme_tab, w.recording_scheme_tab.toolbar),
                     (w.insect_collection_tab, w.insect_collection_tab.toolbar),
                     (w._stats_page, w.stats_reports_tab.section_toggle)):
        w.tabs.setCurrentWidget(tab)
        _pump(qapp, 2)
        assert bar.isVisible() and bar.height() > 0, type(bar).__name__
    w.resize(LIMIT, 900)
    _pump(qapp)
    assert w.width() == LIMIT
    w.resize(1100, 800)
    _pump(qapp)
    assert w.width() == 1100


@pytest.mark.parametrize("metrics_font", ["default", "wide"], indirect=True)
def test_home_scrolls_rather_than_widen(qapp, metrics_font):
    from src.views.home import HomeTab
    from src.views.components.hscroll_strip import PageScroll
    h = HomeTab()
    assert h.minimumSizeHint().width() <= LIMIT
    scroll = h.findChild(PageScroll)
    inner = scroll.widget()
    h.resize(400, 600)
    h.show()
    _pump(qapp)
    bar = scroll.horizontalScrollBar()
    if inner.minimumSizeHint().width() > scroll.viewport().width():
        assert bar.maximum() > 0          # everything still reachable
    h.resize(inner.minimumSizeHint().width() + 40, 900)
    _pump(qapp)
    assert bar.maximum() == 0             # with room for it, Home looks as before
    h.close()


def test_strip_follows_its_widget_and_scrolls_only_when_needed(qapp):
    from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget
    from src.views.components.hscroll_strip import HScrollStrip

    host = QWidget()
    lay = QVBoxLayout(host)
    never_hidden = QPushButton("toolbar")  # built, never shown or hidden: must show
    lay.addWidget(HScrollStrip(never_hidden))
    bar = QWidget()
    bl = QHBoxLayout(bar)
    for i in range(6):
        b = QPushButton(f"b{i}")
        b.setMinimumWidth(100)
        bl.addWidget(b)
    bar.setVisible(False)                  # tabs build their filter bars hidden
    strip = HScrollStrip(bar)
    lay.addWidget(strip)
    host.resize(1200, 300)
    host.show()
    _pump(qapp)
    assert never_hidden.isVisible() and never_hidden.parentWidget().parentWidget().isVisible()
    assert strip.isHidden() and bar.isHidden()
    assert strip.minimumSizeHint().width() <= HScrollStrip.MIN_WIDTH

    bar.setVisible(True)                   # what "Show Filters" does
    _pump(qapp)
    assert strip.isVisible()
    wide_h = strip.height()
    assert strip.horizontalScrollBar().maximum() == 0

    host.resize(300, 300)                  # narrower than the buttons
    _pump(qapp, 6)
    assert strip.horizontalScrollBar().maximum() > 0
    assert strip.height() > wide_h         # room for the scroll bar under the buttons
    assert bar.width() >= bar.minimumSizeHint().width()   # buttons never squashed

    bar.setVisible(False)
    _pump(qapp)
    assert strip.isHidden()
    host.hide()                            # shown again while the parent is hidden
    bar.setVisible(True)
    assert not strip.isHidden()
    host.close()


def test_lazy_page_scrolls_a_page_wider_than_the_window(qapp):
    from PySide6.QtWidgets import QWidget
    from src.views.lazy_tab import LazyTabPage

    def build():
        p = QWidget()
        p.setMinimumWidth(2500)
        return p
    page = LazyTabPage(build, "Wide")
    page.ensure_built()
    assert page.minimumSizeHint().width() <= LIMIT
    assert page.page.minimumWidth() == 2500     # the tab itself is untouched
