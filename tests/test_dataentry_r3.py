"""Round 3 / R9-8 (11 Oct 2026): Data Entry banner display.

* Button text was clipped top and bottom: a fixed 194 px card squeezed the controls' rows.
  Now the banner is as tall as the rows need at the font in use.
* "Back to entry order" sits on the "Showing: ..." line, not in the "Add rows" line.
* On a narrow window the Records legend ran off the right edge; the cards now narrow, and
  Traps then This workbook step aside when even that isn't enough.
* Sorting no longer unticks "Copy context from row above"; nothing is copied while sorted.

Offscreen, on a small temp database.
"""
import gc
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402,F401  (sets up the suite's import paths)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _tidy_widgets(qapp):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    before = set(map(id, QApplication.topLevelWidgets()))
    font = QApplication.font()
    yield
    QApplication.setFont(font)
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


@pytest.fixture
def settings_isolated(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("dataentry_r3")
    QSettings().clear()
    yield
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _make_widget(tmp_path, monkeypatch):
    import sqlite3
    from PySide6.QtWidgets import QMessageBox
    from DataEntry import csv_backup
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT, "
              "record_type TEXT, project_name TEXT, client TEXT)")
    c.commit()
    c.close()
    monkeypatch.setattr(csv_backup, "backup_staging", lambda conn: "s.csv")
    monkeypatch.setattr(csv_backup, "backup_observations", lambda p: "o.csv")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    from DataEntry.data_entry_widget import DataEntryWidget
    return DataEntryWidget(str(db), embedded=True, allow_commit=False)


def _open_grid(w, rows=("Philanthus triangulum", "Abax parallelus", "Carabus violaceus"), **ctx):
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import EntryGridPage
    pid = repo.ensure_personal_job(w._conn)
    for name in rows:
        repo.insert_row(w._conn, pid, dict(species_name=name, species_tvk="T",
                                           date="2026-06-05", **ctx))
    w._open_job(pid)
    return w._job_host.findChildren(EntryGridPage)[-1]


def _pump(qapp, n=4):
    for _ in range(n):
        qapp.processEvents()


def _controls_buttons(g):
    from PySide6.QtWidgets import QCheckBox, QPushButton
    ctl = g._info._controls_widget
    return [b for b in ctl.findChildren(QPushButton) + ctl.findChildren(QCheckBox)
            if not b.isHidden()]


# ---------------------------------------------------------------- 1. button text not clipped

@pytest.mark.parametrize("family,pt", [(None, 9), (None, 11), (None, 13), ("DejaVu Sans", 13)])
def test_banner_buttons_get_their_full_height(qapp, settings_isolated, tmp_path, monkeypatch,
                                              family, pt):
    """At any font, every control button is at least as tall as it asks to be, and that is at
    least the text's height plus the padding (3 px top and bottom)."""
    from PySide6.QtGui import QFont, QFontMetrics
    from PySide6.QtWidgets import QApplication, QPushButton
    f = QFont(family or QApplication.font().family())
    f.setPointSize(pt)
    QApplication.setFont(f)
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    w.resize(1920, 900)
    w.show()
    _pump(qapp)
    for sorted_ in (False, True):
        if sorted_:
            g._on_header_sort(0)
            _pump(qapp)
        buttons = _controls_buttons(g)
        texts = {b.text() for b in buttons}
        assert {"+10", "+100", "+1000", "Remove empty tail", "Count mode (F9)",
                "Export…", "Discard job"} <= texts
        assert ("Back to entry order" in texts) == sorted_
        for b in buttons:
            assert b.height() >= b.sizeHint().height(), (b.text(), b.height(), b.sizeHint())
            assert b.width() >= b.sizeHint().width(), b.text()
            if isinstance(b, QPushButton):
                text_h = QFontMetrics(b.font()).height()
                assert b.height() >= text_h + 2 * 3, (b.text(), b.height(), text_h)
            # nothing drawn below the card's bottom edge
            bottom = b.mapTo(g._info._controls_widget, b.rect().bottomLeft()).y()
            assert bottom < g._info._controls_widget.height(), b.text()
    w.close()


def test_banner_grows_when_a_card_needs_more_height(qapp):
    from PySide6.QtWidgets import QVBoxLayout, QWidget
    from DataEntry.banner_layout import banner_height
    small, tall = QWidget(), QWidget()
    for wdg, h in ((small, 50), (tall, 260)):
        lay = QVBoxLayout(wdg)
        inner = QWidget()
        inner.setMinimumHeight(h)
        lay.addWidget(inner)
    assert banner_height(194, [small]) == 194
    assert banner_height(194, [small, tall]) >= 260


def test_compact_buttons_keep_the_colour_system(qapp):
    from DataEntry import theme
    for fn in (theme.button_primary_qss, theme.button_secondary_qss, theme.button_delete_qss):
        assert "padding: 6px" in fn() and "padding: 3px" in fn(compact=True)
        assert fn().replace("padding: 6px", "padding: 3px") == fn(compact=True)


# ---------------------------------------------------------------- 2. Back to entry order

def test_back_to_entry_order_is_on_the_showing_line(qapp, settings_isolated, tmp_path, monkeypatch):
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    w.resize(1920, 900)
    w.show()
    _pump(qapp)
    btn, lbl = g._sort_btn, g._order_lbl
    plus1000 = next(b for b in _controls_buttons(g) if b.text() == "+1000")
    # the same layout row as the label, not the add-rows row
    top = g._info._controls_widget.layout()
    rows = [top.itemAt(i).layout() for i in range(top.count()) if top.itemAt(i).layout()]
    row_of = lambda wdg: next(r for r in rows if r.indexOf(wdg) >= 0)  # noqa: E731
    assert row_of(btn) is row_of(lbl)
    assert row_of(btn) is not row_of(plus1000)
    assert btn.isHidden()
    h_before = g._info.banner_height()
    y_lbl = lbl.mapTo(w, lbl.rect().center()).y()
    g._on_header_sort(0)
    _pump(qapp)
    assert not btn.isHidden()
    assert abs(btn.mapTo(w, btn.rect().center()).y() - y_lbl) <= 2   # same line
    assert btn.geometry().left() > lbl.geometry().right()            # just after the label
    assert g._info.banner_height() == h_before                       # nothing jumps
    btn.click()
    _pump(qapp)
    assert btn.isHidden() and lbl.text() == "Showing: entry order"
    w.close()


# ---------------------------------------------------------------- 3. narrow windows

def _set_metrics(qapp, metrics):
    """"wide" stands in for text that measures much wider than the Linux test fonts (Wil's PC
    forced the window to 1563 px): every label's letters are spaced to 200 %. Style sheets set
    sizes in px only, so the spacing reaches every label, button and check box."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    if metrics == "wide":
        f = QFont(QApplication.font())
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 200)
        QApplication.setFont(f)


@pytest.mark.parametrize("metrics", ["default", "wide"])
@pytest.mark.parametrize("width", [1920, 1500, 1280, 1150])
def test_banner_cards_fit_the_window(qapp, settings_isolated, tmp_path, monkeypatch, width,
                                     metrics):
    """Whatever the font measures, the Data Entry widget never forces the window wider: the
    cards narrow, Traps then This workbook step aside, and in the worst case a scroll bar
    appears under the banner. Nothing is drawn past the right edge of what is in view."""
    from DataEntry.banner_layout import ElidedCheckBox
    _set_metrics(qapp, metrics)
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    w.resize(width, 900)
    w.show()
    _pump(qapp, 6)
    ip, scroll = g._info, g._banner_scroll
    assert w.width() == width                       # the banner doesn't force the window wider
    assert w.minimumSizeHint().width() <= width
    view_w = scroll.viewport().width()
    bar = scroll.horizontalScrollBar()
    if ip.width() > view_w:                         # can't fit even the cards that must stay
        assert bar.maximum() > 0 and bar.isVisible()
        assert ip.width() == ip.minimumWidth()      # ...and no wider than that
    else:
        assert bar.maximum() == 0 and not bar.isVisible()
    shown = [c for c in ip._banner_cards if c.isVisible()]
    for c in shown:
        right = c.mapTo(ip, c.rect().topRight()).x()
        assert right < ip.width(), (width, right, ip.width())
        assert c.width() >= ip._least_width(c), (width, c.width(), ip._least_width(c))
    # the readout, the controls, and (with a map) the maps and legend always stay
    assert ip._banner_cards[0] in shown and ip._controls_widget in shown
    assert all(c in shown for c in ip._banner_cards if c not in ip._collapsible)
    # Traps steps aside first, This workbook only after it
    traps, workbook = ip._collapsible
    assert not (workbook.isHidden() and not traps.isHidden())
    # every card is shown when, measured at this font, the row can hold them all
    fits_all = ip._row_width(ip._banner_cards) <= view_w
    assert fits_all == all(c.isVisible() for c in ip._banner_cards), (width, fits_all)
    if metrics == "default" and width >= 1900 and sys.platform.startswith("linux"):
        assert fits_all                             # Linux test fonts: room for every card
    legend = [c for c in ip.findChildren(ElidedCheckBox)]
    for chk in legend:                              # whole labels, or "..." with the label on hover
        assert chk.text() == chk.full_text() or (chk.text().endswith("…")
                                                 and chk.toolTip() == chk.full_text())
    # widen again: every card comes back if there is room for it
    w.resize(1920, 900)
    _pump(qapp, 6)
    assert w.width() == 1920
    fits_all = ip._row_width(ip._banner_cards) <= scroll.viewport().width()
    assert fits_all == all(c.isVisible() for c in ip._banner_cards)
    w.close()


@pytest.mark.parametrize("metrics", ["default", "wide"])
def test_banner_refits_when_back_to_entry_order_appears(qapp, settings_isolated, tmp_path,
                                                        monkeypatch, metrics):
    """Sorting shows "Back to entry order", widening the controls' Showing line: the banner
    measures again, so the controls card is never squeezed below its contents."""
    _set_metrics(qapp, metrics)
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    w.resize(1150, 900)
    w.show()
    _pump(qapp, 6)
    ctl = g._info._controls_widget
    g._on_header_sort(0)
    _pump(qapp, 6)
    assert not g._sort_btn.isHidden()
    assert ctl.width() >= ctl.minimumSizeHint().width()
    assert g._sort_btn.width() >= g._sort_btn.sizeHint().width()
    assert w.width() == 1150
    w.close()


def test_data_entry_labels_wrap_rather_than_widen(qapp, settings_isolated, tmp_path, monkeypatch):
    """The notice line, the job heading and the status line wrap on a narrow window; they
    don't set a minimum width on it (R3: the notice alone needed ~730 px at Linux fonts)."""
    from PySide6.QtWidgets import QLabel
    w = _make_widget(tmp_path, monkeypatch)
    _open_grid(w)
    assert w.layout().itemAt(0).widget().wordWrap()           # the notice line
    assert w._status.wordWrap()                                # the status line
    heading = [lab for lab in w._job_host.findChildren(QLabel) if "<b>" in lab.text()]
    assert heading and all(lab.wordWrap() for lab in heading)  # the job heading
    w.resize(500, 600)
    w.show()
    _pump(qapp)
    assert w.layout().itemAt(0).widget().minimumSizeHint().width() < 500
    w.close()


def test_elided_checkbox_shortens_and_restores(qapp):
    from DataEntry.banner_layout import ElidedCheckBox
    c = ElidedCheckBox("Insect Collection")
    c.resize(400, 20)
    c.show()
    qapp.processEvents()
    assert c.text() == "Insect Collection" and c.toolTip() == ""
    c.resize(60, 20)
    qapp.processEvents()
    assert c.text().endswith("…") and c.toolTip() == "Insect Collection"
    assert c.minimumSizeHint().width() < c.sizeHint().width()
    c.resize(400, 20)
    qapp.processEvents()
    assert c.text() == "Insect Collection"
    c.close()


# ---------------------------------------------------------------- 4. copy context and sorting

def test_sorting_leaves_copy_context_tick_alone(qapp, settings_isolated, tmp_path, monkeypatch):
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w)
    assert g._copy_ctx.isChecked() and g._model.copies_context()
    g._on_header_sort(0)
    assert g._copy_ctx.isChecked()                  # the tick is the user's
    assert not g._model.copies_context()            # but nothing is copied while sorted
    g._sort_btn.click()
    assert g._copy_ctx.isChecked() and g._model.copies_context()
    # unticked by the user: sorting and un-sorting keep it unticked
    g._copy_ctx.setChecked(False)
    g._on_header_sort(0)
    g._sort_btn.click()
    assert not g._copy_ctx.isChecked() and not g._model.copies_context()
    w.close()


def test_no_context_copied_while_sorted(qapp, settings_isolated, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from DataEntry.entry_grid import COLIDX
    w = _make_widget(tmp_path, monkeypatch)
    g = _open_grid(w, rows=("Abax parallelus", "Carabus violaceus"),
                   grid_ref="SP4030", site_name="Wood")
    m = g._model

    def pick(name):
        r = len(m._rows)                           # the first empty row, under the last record
        m.setData(m.index(r, COLIDX["species_name"]), {"scientific_name": name, "tvk": "T2"},
                  Qt.ItemDataRole.EditRole)
        return m._rows[r]

    row = pick("Philanthus triangulum")             # entry order: copied from the row above
    assert row["site_name"] == "Wood" and row["grid_ref"] == "SP4030"
    g._on_header_sort(COLIDX["species_name"])
    row = pick("Bombus terrestris")                 # sorted: the tick stays, nothing copied
    assert g._copy_ctx.isChecked()
    assert not row.get("site_name") and not row.get("grid_ref")
    w.close()
