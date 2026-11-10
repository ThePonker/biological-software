"""Builds the manual's screenshots: python Lector/docs/manual/make_screens.py [output folder]

Makes a small demo lector.db in a temporary folder (invented searches, pages and text; no
network), opens each Lector screen offscreen, saves a PNG of it, and draws the numbered
callouts from callouts.py (circles with numbers and thin leader lines, in the theme's colours).
Run it again after the screens change, then check manual.md still matches the numbers.

Output folder: Lector/docs/manual/screens by default. To use your own screenshots instead,
replace the PNG of the same name in that folder (manual.md says how).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (str(ROOT), str(ROOT / "Observatum"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import callouts  # noqa: E402
import demo  # noqa: E402

SHOTS = ("saved_searches", "builder", "search_page", "reading_list", "tags", "records",
         "record_form", "exports", "api_key")
SIZE = (1360, 860)
RADIUS = 13


def resolve(target, win, dialog=None):
    """The widget a callout points at, or None. See callouts.py for the two forms."""
    if target.startswith("attr:"):
        path = target[5:].split(".")
        obj = win
        if path[0] == "dialog":
            obj, path = dialog, path[1:]
        for part in path:
            if obj is None:
                return None
            obj = obj.get(part) if isinstance(obj, dict) else getattr(obj, part, None)
        return obj if isinstance(obj, QWidget) else None
    root = dialog or win
    return root.findChild(QWidget, target)


def draw_callouts(pixmap, frame, shot, win, dialog=None, table=callouts.CALLOUTS):
    """Draw the numbered circles for one screen on the pixmap of `frame`. Returns the
    (number, label) pairs drawn and the targets that could not be found."""
    from Lector.ui import style as S
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    line = QPen(QColor(S.ACCENT_DARK), 1.4)
    drawn, missing = [], []
    for screen, target, number, label in table:
        if screen != shot:
            continue
        w = resolve(target, win, dialog)
        if w is None or not w.isVisibleTo(frame):
            missing.append(target)
            continue
        top_left = w.mapTo(frame, QPoint(0, 0))
        rect = QRect(top_left, w.size()).intersected(frame.rect())
        centre = QPoint(max(RADIUS + 2, rect.left() - 6), max(RADIUS + 2, rect.top() - 6))
        painter.setPen(line)
        painter.drawLine(centre, QPoint(rect.left() + 10, rect.top() + 10))
        painter.setBrush(QColor(S.ACCENT_DARK))
        painter.drawEllipse(rect.left() + 7, rect.top() + 7, 6, 6)
        painter.setBrush(QColor(S.ACCENT))
        painter.setPen(QPen(QColor(S.c("surface")), 2))
        painter.drawEllipse(centre, RADIUS, RADIUS)
        painter.setPen(QColor(S.c("primary_text")))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(QRect(centre.x() - RADIUS, centre.y() - RADIUS, 2 * RADIUS, 2 * RADIUS),
                         Qt.AlignmentFlag.AlignCenter, str(number))
        drawn.append((number, label))
    painter.end()
    return drawn, missing


def _settle(app, n=4):
    for _ in range(n):
        app.processEvents()


def _grab(app, widget, path, shot, win, dialog=None):
    widget.show()
    _settle(app)
    pix = widget.grab()
    drawn, missing = draw_callouts(pix, widget, shot, win, dialog)
    pix.save(str(path), "PNG")
    return drawn, missing


def make_screens(out_dir, work_dir=None, shots=SHOTS):
    """Write the PNGs into out_dir. Returns {shot: {'file', 'callouts', 'missing'}}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    from Lector.ui.app import LectorWindow
    from Lector.ui.apikey_dialog import ApiKeyDialog
    from Lector.ui.record_dialog import RecordDialog
    from Lector.ui.tags_dialog import TagsDialog
    work = Path(work_dir or tempfile.mkdtemp(prefix="lector_manual_"))
    from PySide6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)       # remembered filters stay in the work folder
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(work / "qt"))
    svc, ids = demo.build(work)
    win = LectorWindow(svc, quiet=True)
    win.resize(*SIZE)
    win.show()
    win.start()
    _settle(app)
    win.resize(*SIZE)              # fit_to_screen shrank it to the offscreen screen: undo that
    _settle(app)
    result, dialogs = {}, []

    def record(shot, widget, dialog=None):
        # the foot of the menu: not this computer's temp folder or key
        win.key_link.setText("BHL API key: set")
        win.nav_info.setText("Database: C:\\Users\\you\\Documents\\Lector\\data\\lector.db")
        drawn, missing = _grab(app, widget, out_dir / f"{shot}.png", shot, win, dialog)
        result[shot] = {"file": f"{shot}.png", "callouts": drawn, "missing": missing}

    for shot in shots:
        if shot == "saved_searches":
            win.go("searches")
            record(shot, win)
        elif shot == "builder":
            win.go("builder", search_id=None)
            win.screens["builder"].species_edit.setText("Lamia textor")
            win.screens["builder"].find_species()
            record(shot, win)
        elif shot == "search_page":
            win.go("history", search_id=ids["lamia"])
            record(shot, win)
        elif shot == "reading_list":
            win.go("review", search_id=ids["lamia"], status="all")
            screen = win.screens["review"]
            screen.show_box.setCurrentIndex(max(screen.show_box.findData("all"), 0))
            screen.filters.hide_nr.setChecked(False)
            screen._filters_changed(reload=True)
            record(shot, win)
        elif shot == "tags":
            win.go("review", search_id=ids["lamia"])
            dlg = TagsDialog(svc, win)
            dlg.resize(520, 420)
            dialogs.append(dlg)
            record(shot, dlg, dlg)
        elif shot == "records":
            win.go("records")
            win.screens["records"].table.selectRow(0)
            record(shot, win)
        elif shot == "record_form":
            page = svc.review_queue(ids["lamia"])[0]
            dlg = RecordDialog(svc, ids["lamia"], page["page_id"], parent=win)
            dlg.resize(720, 820)
            dlg.edits["date_printed"].setText("14th June 1868")
            dlg.edits["place"].setText("Darenth Wood, near Dartford")
            dlg.edits["grid_ref"].setText("TQ5571")
            dlg.edits["recorder"].setText("Mr. J. Smith")
            dlg.day.setValue(14)
            dlg.month.setValue(6)
            dlg.year.setValue(1868)
            dlg.vc.setValue(16)
            dialogs.append(dlg)
            record(shot, dlg, dlg)
        elif shot == "exports":
            win.go("export", search_id=ids["lamia"])
            win.screens["export"].save_to.setText(
                "Saved to C:\\Users\\you\\Documents\\Lector\\data\\lector_exports")
            record(shot, win)
        elif shot == "api_key":
            dlg = ApiKeyDialog(svc, win, first_run=True)
            dlg.key_edit.setText("paste-your-key-here")
            dialogs.append(dlg)
            record(shot, dlg, dlg)
    for d in dialogs:
        d.close()
    win.close()
    app.processEvents()
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else HERE / "screens"
    result = make_screens(out)
    for shot, info in result.items():
        print(f"{info['file']}: {len(info['callouts'])} callouts"
              + (f"  (not found: {', '.join(info['missing'])})" if info["missing"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
