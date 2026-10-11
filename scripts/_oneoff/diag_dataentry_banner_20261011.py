"""diag_dataentry_banner_20261011.py -- READ ONLY: how wide the Data Entry banner measures here.

    py -3.14 scripts\\_oneoff\\diag_dataentry_banner_20261011.py           # offscreen, like the tests
    py -3.14 scripts\\_oneoff\\diag_dataentry_banner_20261011.py --show    # on the real screen

Why
---
tests/test_dataentry_r3.py::test_banner_cards_fit_the_window failed on Wil's PC (11 Oct): the
window could not be made narrower than 1563 px, and at 1920 a card was stepped aside. On Linux
the same test passes. This prints what the banner's cards measure on this machine (screen DPI
and scale, the font, each card's least / preferred / actual width and whether it is shown), so
the cause can be seen rather than guessed.

What it touches
---------------
Nothing of yours. Like the test, it builds the Data Entry widget on a NEW temporary
observatum.db in a new temp folder (one empty observations table plus the staging tables the
widget creates), with three made-up rows in the Personal job. data/observatum.db and the
staging tables in it are never opened. Reference data (codex.db, vc_lookup.db, the maps) are
opened read-only, as the app does. The species search is replaced by a stand-in so
observatum.db / uksi.db are not opened at all. CSV backups are switched off, and Qt settings go
to an .ini file in the temp folder (not the registry). The temp folder is left in place and its
path printed; it is safe to delete.
"""
from __future__ import annotations

import argparse
import os
import platform
import sqlite3
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

WIDTHS = (1920, 1500, 1280)
REF_TEXT = "Export for iRecord  Remove empty tail  Copy context from row above"
REF_LINUX = 388   # REF_TEXT at 12 px in the Linux test font (Inter), for comparison


class _NoSearch:
    """Stand-in for the species search service: present (so the controls card is built as in
    the app, without the 'species popup unavailable' note) but it never opens a database."""

    def __bool__(self):
        return True

    def __getattr__(self, name):
        return lambda *a, **k: []


def _temp_db(folder: str) -> str:
    db = os.path.join(folder, "observatum.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT, "
              "record_type TEXT, project_name TEXT, client TEXT)")
    c.commit()
    c.close()
    return db


def _pump(app, n=6):
    for _ in range(n):
        app.processEvents()


def _card_names(ip):
    names = {}
    cards = list(ip._banner_cards)
    if cards:
        names[id(cards[0])] = "Readout"
    coll = list(getattr(ip, "_collapsible", []))
    if len(coll) == 2:
        names[id(coll[0])] = "Traps"
        names[id(coll[1])] = "This workbook"
    if ip._controls_widget is not None:
        names[id(ip._controls_widget)] = "Controls"
    rest = [c for c in cards if id(c) not in names]
    for c, n in zip(rest, ("Maps", "Legend")):
        names[id(c)] = n
    return [(names.get(id(c), "?"), c) for c in cards]


def _report(app, w, g, width):
    w.resize(width, 900)
    w.show()
    _pump(app)
    ip = g._info
    scroll = getattr(g, "_banner_scroll", None)
    print(f"\n--- window asked {width} px: got {w.width()} px ---")
    print(f"  Data Entry widget minimumSizeHint: {w.minimumSizeHint().width()} px"
          f"   (minimumWidth {w.minimumWidth()})")
    lay = w.layout()
    for i in range(lay.count()):
        it = lay.itemAt(i)
        wd = it.widget()
        kind = type(wd).__name__ if wd is not None else "item"
        print(f"    row {i}: {kind:16s} least {it.minimumSize().width():5d}  "
              f"wants {it.sizeHint().width():5d}")
    if scroll is not None:
        bar = scroll.horizontalScrollBar()
        print(f"  banner: view {scroll.viewport().width()} px, banner {ip.width()} px "
              f"(least {ip.minimumWidth()}), scroll bar {'SHOWN' if bar.isVisible() else 'off'}")
    else:
        print(f"  banner: {ip.width()} px (least {ip.minimumWidth()}) -- no scroll area "
              "(code before the R3 fix)")
    print(f"  {'card':14s} {'least':>6s} {'minHint':>8s} {'hint':>6s} {'width':>6s}  shown")
    least = getattr(ip, "_least_width", None)
    for name, c in _card_names(ip):
        lw = least(c) if least else c.minimumWidth()
        print(f"  {name:14s} {lw:6d} {c.minimumSizeHint().width():8d} "
              f"{c.sizeHint().width():6d} {c.width():6d}  {'yes' if c.isVisible() else 'NO'}")
    if hasattr(ip, "_row_width"):
        print(f"  all cards at their least: {ip._row_width(ip._banner_cards)} px; "
              f"the ones that must stay: "
              f"{ip._row_width([c for c in ip._banner_cards if c not in ip._collapsible])} px")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--show", action="store_true",
                    help="use the real screen (default: offscreen, as the tests do)")
    args = ap.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import paths  # noqa: F401  (the suite's import paths)
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QCoreApplication, QSettings, qVersion
    from PySide6.QtGui import QFont, QFontInfo, QFontMetrics
    from PySide6.QtWidgets import QApplication, QMessageBox

    folder = tempfile.mkdtemp(prefix="diag_dataentry_banner_")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    app = QApplication.instance() or QApplication(sys.argv)
    QCoreApplication.setOrganizationName("ObservatumDiag")
    QCoreApplication.setApplicationName("diag_dataentry_banner")

    scr = app.primaryScreen()
    f = app.font()
    fi = QFontInfo(f)
    ref = QFont(f)
    ref.setPixelSize(12)
    print("Data Entry banner diagnostic -- READ ONLY")
    print(f"  platform:  {platform.platform()}   Python {platform.python_version()}")
    print(f"  Qt {qVersion()}, PySide6 {pyside_version}, Qt platform plugin: "
          f"{app.platformName()}")
    print(f"  screen:    {scr.name()!r} {scr.geometry().width()}x{scr.geometry().height()}, "
          f"logical DPI {scr.logicalDotsPerInch():.0f}, physical DPI "
          f"{scr.physicalDotsPerInch():.0f}, scale (devicePixelRatio) {scr.devicePixelRatio()}")
    print(f"  app font:  {f.family()!r} {f.pointSizeF()} pt (pixel size {f.pixelSize()}); "
          f"really drawn with {fi.family()!r} at {fi.pixelSize()} px")
    adv = QFontMetrics(ref).horizontalAdvance(REF_TEXT)
    print(f"  reference: {REF_TEXT!r} at 12 px measures {adv} px "
          f"(Linux test font: {REF_LINUX} px, so x{adv / REF_LINUX:.2f})")
    print(f"  temp folder (safe to delete afterwards): {folder}")

    from DataEntry import bootstrap, csv_backup
    from DataEntry import staging_repo as repo
    csv_backup.backup_staging = lambda conn: None
    csv_backup.backup_observations = lambda p: None
    bootstrap.get_search_service_safe = lambda: _NoSearch()
    QMessageBox.question = lambda *a, **k: QMessageBox.StandardButton.No

    from DataEntry.data_entry_widget import DataEntryWidget
    from DataEntry.entry_grid import EntryGridPage
    db = _temp_db(folder)
    w = DataEntryWidget(db, embedded=True, allow_commit=False)
    pid = repo.ensure_personal_job(w._conn)
    for name in ("Philanthus triangulum", "Abax parallelus", "Carabus violaceus"):
        repo.insert_row(w._conn, pid, dict(species_name=name, species_tvk="T",
                                           date="2026-06-05"))
    w._open_job(pid)
    g = w._job_host.findChildren(EntryGridPage)[-1]
    for width in WIDTHS:
        _report(app, w, g, width)
    w.close()
    _pump(app)
    print("\nREAD ONLY -- nothing in data/ was opened for writing; only the temp folder above.")


if __name__ == "__main__":
    main()
