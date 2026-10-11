"""Laptop screens (R5, 11 Oct 2026).

The first install of the suite is on a laptop: 1366 x 768, or 1920 x 1080 at 150 %
(= 1280 x 720 logical). Less a 48 px taskbar, 1280 x 720 leaves 1280 x 672 of desktop, and
a window's title bar and frame take about 32 x 8 of that. Several dialogs and windows were
taller than that (Add / Edit Specimen 780, the import wizards 800+, the Recording Scheme's
Status filter 750, VC details 707, Achievements 950, Examen 700, Curator 800, Munia 960,
Munia's Budget Settings 710), so their buttons were below the screen's edge.

Each fixed window must now be able to shrink to the free desktop at 1280 x 720, its
buttons still on screen, at the test fonts; with "wide" text (every letter spaced to
200 %, standing in for fonts that measure much wider -- see tests/test_window_width_r4.py)
its height must still fit. Heights don't depend on how wide a font measures.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

AVAIL_W, AVAIL_H = 1280, 672             # 1280 x 720 less the taskbar
LIMIT_W, LIMIT_H = AVAIL_W - 8, AVAIL_H - 32   # less the window frame and title bar

HAVE_DATA = all(p.exists() for p in (paths.OBSERVATUM_DB, paths.UKSI_DB, paths.CODEX_DB,
                                     paths.PANTHEON_DB))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="real data copies not present")


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


@pytest.fixture(autouse=True)
def _tidy(qapp):
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    before = set(map(id, QApplication.topLevelWidgets()))
    yield
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.hide()
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def _pump(qapp, n=4):
    for _ in range(n):
        qapp.processEvents()


def _minimum(w):
    msh, ms = w.minimumSizeHint(), w.minimumSize()
    return max(msh.width(), ms.width()), max(msh.height(), ms.height())


def _check_fits(qapp, w, button_texts=()):
    """The window can be as small as the free desktop, and at that size the named buttons
    are inside it (not clipped, not below the edge).

    With "wide" text only the height is checked: letter spacing makes text wider, not
    taller, and a row of buttons is as wide as its words (on Wil's PC, where offscreen
    text already measures about as wide as "wide" does here, "wide" doubles it again)."""
    from PySide6.QtWidgets import QAbstractButton, QApplication
    wide = QApplication.font().letterSpacing() > 0
    mw, mh = _minimum(w)
    assert mh <= LIMIT_H, (type(w).__name__, mw, mh)
    assert wide or mw <= LIMIT_W, (type(w).__name__, mw, mh)
    w.show()
    _pump(qapp)
    w.resize(min(w.width(), LIMIT_W), min(w.height(), LIMIT_H))
    _pump(qapp)
    assert w.height() <= LIMIT_H, (w.width(), w.height())
    assert wide or w.width() <= LIMIT_W, (w.width(), w.height())
    texts = {b.text().replace("&", ""): b for b in w.findChildren(QAbstractButton)
             if b.isVisible()}
    for t in button_texts:
        b = texts.get(t)
        assert b is not None, (t, sorted(texts))
        br = b.mapTo(w, b.rect().bottomRight())
        assert 0 < br.y() <= w.height(), (t, br)
        assert wide or 0 < br.x() <= w.width(), (t, br)
        assert not b.visibleRegion().isEmpty(), t
    return mw, mh


FONTS = pytest.mark.parametrize("metrics_font", ["default", "wide"], indirect=True)


# ----------------------------------------------------------------- the helper itself

def test_place_shrinks_centres_and_keeps_inside(qapp):
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget
    from shared.fit_to_screen import FRAME, TITLE_BAR, place
    avail = QRect(0, 0, AVAIL_W, AVAIL_H)
    w = QWidget()
    w.setMinimumSize(300, 200)
    w.resize(1200, 1000)                         # taller than the screen
    place(w, avail)
    assert (w.width(), w.height()) == (1200, AVAIL_H - TITLE_BAR)
    assert w.y() == 0 and 0 <= w.x() <= AVAIL_W - 1200 - FRAME
    w.resize(400, 300)                           # fits: keeps its size, centred
    place(w, avail)
    assert (w.width(), w.height()) == (400, 300)
    assert abs(w.x() + (400 + FRAME) // 2 - AVAIL_W // 2) <= 1
    assert abs(w.y() + (300 + TITLE_BAR) // 2 - AVAIL_H // 2) <= 1
    w.setMinimumSize(1400, 800)                  # can't fit: never below its minimum
    place(w, avail)
    assert (w.width(), w.height()) == (1400, 800) and (w.x(), w.y()) == (0, 0)


def test_fit_to_screen_waits_for_show_and_keeps_natural_size(qapp):
    from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget
    from shared.fit_to_screen import fit_to_screen, scroll_body
    d = QDialog()
    body = QWidget()
    lay = QVBoxLayout(body)
    for i in range(40):
        lay.addWidget(QLabel(f"row {i}"))
    QVBoxLayout(d).addWidget(scroll_body(body))
    fit_to_screen(d)
    # the body scrolls: the dialog's minimum no longer grows with it...
    assert _minimum(d)[1] < body.minimumSizeHint().height()
    # ...but it asks for the body's whole height, as it did without the scroll area
    assert d.sizeHint().height() >= body.sizeHint().height()
    avail = qapp.primaryScreen().availableGeometry()
    d.show()
    _pump(qapp)
    want = min(d.sizeHint().height(), avail.height() - 32)
    assert d.height() == want
    assert avail.contains(d.pos())


# ----------------------------------------------------------------- Observatum dialogs

@FONTS
def test_add_and_edit_specimen(qapp, metrics_font, tmp_path):
    from src.views.dialogs.add_specimen_dialog import AddSpecimenDialog
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name, species_tvk, "
              "date, grid_ref, site_name, recorder, quantity, sex, record_type, project_name)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, specimen_code, species_name, "
              "species_tvk, date_collected, grid_ref, collector, site_name, observation_id, "
              "sex, updated_at)")
    c.execute("INSERT INTO specimens VALUES (1,'S1','Aa','T1','2025-06-01','SP123456',"
              "'Heeney','Wood',NULL,NULL,NULL)")
    c.commit()
    c.close()
    _check_fits(qapp, AddSpecimenDialog(None, None, None, obs_db_path=str(db)),
                ["Cancel"])
    spec = dict(id=1, specimen_code="S1", species_name="Aa", species_tvk="T1",
                date_collected="2025-06-01", grid_ref="SP123456", collector="Heeney",
                site_name="Wood")
    _check_fits(qapp, AddSpecimenDialog(None, None, None, existing_specimen=spec,
                                        obs_db_path=str(db)), ["Cancel"])


@FONTS
@pytest.mark.parametrize("kind", ["observation", "scheme", "specimen"])
def test_import_wizards(qapp, metrics_font, kind):
    if kind == "observation":
        from src.views.dialogs.observation_import_wizard.observation_import_wizard import \
            ObservationImportWizard as W
    elif kind == "scheme":
        from src.views.dialogs.scheme_import_wizard.scheme_import_wizard import \
            SchemeImportWizard as W
    else:
        from src.views.dialogs.specimen_import_wizard.specimen_import_wizard import \
            SpecimenImportWizard as W
    w = W(parent=None, uksi_model=None, vc_service=None, db=None)
    _check_fits(qapp, w)
    # every step: Back / Next / Cancel stay inside the window, the step scrolls
    for i in range(w.stack.count()):
        w.stack.setCurrentIndex(i)
        _pump(qapp, 2)
        for b in (w.cancel_btn, w.back_btn, w.next_btn):
            if not b.isVisible():
                continue
            br = b.mapTo(w, b.rect().bottomRight())
            assert br.y() <= w.height(), (i, b.text())


@FONTS
def test_status_filter_with_datasets(qapp, metrics_font):
    from src.views.components.filter_wizard.status_filter_dialog import StatusFilterDialog
    d = StatusFilterDialog(dataset_list=[(f"Dataset {i}", i * 10) for i in range(12)])
    _check_fits(qapp, d, ["Apply Filters", "Clear"])
    plain = StatusFilterDialog()               # without datasets: as before, no scrolling
    plain.show()
    _pump(qapp)
    from shared.fit_to_screen import BodyScroll
    assert plain.findChild(BodyScroll).verticalScrollBar().maximum() == 0


@FONTS
def test_vc_details(qapp, metrics_font):
    from src.views.stats.scheme_dashboard import VCDetailsDialog
    _check_fits(qapp, VCDetailsDialog(23, "Oxfordshire", {}), ["Close", "Export CSV"])


@FONTS
def test_achievements(qapp, metrics_font, monkeypatch):
    import src.features.gamification.window as gw

    class NoCalc:
        def __getattr__(self, name):
            return lambda *a, **k: {}

    monkeypatch.setattr(gw, "ensure_gamification_db", lambda: True)
    monkeypatch.setattr(gw, "GamificationCalculator", NoCalc)
    monkeypatch.setattr(gw.GamificationWindow, "_load_data", lambda self: None)
    monkeypatch.setattr(gw.GamificationWindow, "showEvent",
                        lambda self, e: super(gw.GamificationWindow, self).showEvent(e))
    _check_fits(qapp, gw.GamificationWindow(), ["Close"])


@needs_data
@FONTS
def test_drawer_in_hand(qapp, metrics_font):
    from src.views.collection.drawer_assign_dialog import DrawerAssignDialog
    _check_fits(qapp, DrawerAssignDialog(None, db_path=paths.OBSERVATUM_DB))


# ----------------------------------------------------------------- other apps

@FONTS
def test_munia_window_and_budget(qapp, metrics_font, tmp_path, monkeypatch):
    from Munia import munia_data
    monkeypatch.setattr(munia_data, "DB_PATH", tmp_path / "munia.db")
    from Munia.munia_ui import MuniaWindow
    w = MuniaWindow()
    _check_fits(qapp, w)
    from Munia.budget_settings import BudgetSettingsDialog
    conn = munia_data.get_connection()
    munia_data.ensure_schema(conn)
    _check_fits(qapp, BudgetSettingsDialog(conn, 2026), ["Save", "Cancel"])
    w.close()


@needs_data
@FONTS
def test_examen_window(qapp, metrics_font):
    from PySide6.QtWidgets import QPushButton
    from Examen.examen_ui import ExamenWindow
    from src.views.components.hscroll_strip import HScrollStrip
    e = ExamenWindow()
    e.resize(LIMIT_W, LIMIT_H)
    e.show()
    _pump(qapp)
    e.tabs.setCurrentWidget(e.analysis_view)
    _pump(qapp, 6)
    _check_fits(qapp, e)
    # the toolbar row's buttons sit inside their strip (they were 7 px low and cut off)
    strip = e.analysis_view.findChild(HScrollStrip)
    box = strip.widget()
    _pump(qapp, 4)
    assert box.layout().geometry() == box.rect()
    for b in box.findChildren(QPushButton):
        assert b.geometry().bottom() <= box.rect().bottom(), b.text()
    e.close()


@needs_data
@FONTS
def test_curator_window(qapp, metrics_font):
    from Curator.planner_ui import PlannerWindow
    w = PlannerWindow()
    _check_fits(qapp, w)
    w.close()


def test_data_entry_standalone_is_fitted(qapp, tmp_path, monkeypatch):
    """Data Entry on its own opened at 860 x 720: taller than a laptop's free screen. Now
    it opens no taller than the screen it is on (the test screen is smaller still)."""
    import importlib
    from PySide6.QtWidgets import QApplication
    from DataEntry import csv_backup
    de_main = importlib.import_module("DataEntry.__main__")
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT, "
              "record_type TEXT, project_name TEXT, client TEXT)")
    c.commit()
    c.close()
    monkeypatch.setattr(de_main, "_resolve_main_db", lambda explicit: (str(db), None))
    monkeypatch.setattr(de_main.bootstrap, "init_databases", lambda m, u: (None, None))
    monkeypatch.setattr(csv_backup, "backup_staging", lambda conn: "s.csv")
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    org, name = qapp.organizationName(), qapp.applicationName()
    try:
        assert de_main.main([]) == 0
    finally:
        qapp.setOrganizationName(org)
        qapp.setApplicationName(name)
    from DataEntry.data_entry_widget import DataEntryWidget
    w = [t for t in QApplication.topLevelWidgets() if isinstance(t, DataEntryWidget)][-1]
    _pump(qapp)
    avail = qapp.primaryScreen().availableGeometry()
    assert w.height() <= max(avail.height() - 32, _minimum(w)[1])
    assert w.width() == 860 or w.width() <= avail.width() - 8
    w.close()
