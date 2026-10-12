"""Lector desktop window: left navigation, one screen at a time, background tasks.

    python -m Lector gui            (launchers/run_lector_gui.bat, Atrium's Lector tile)

Every screen talks to LectorService only (no SQL, no BHL here). Anything that may
take a while (BHL counts, previews, runs, exports) goes through self.tasks
(workers.TaskRunner): the progress line at the bottom shows it and its Cancel stops
it; closing the window cancels a task and closes once it has stopped.
"""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QProgressBar, QStackedWidget,
                               QVBoxLayout, QWidget)

from Lector import config
from Lector.service import LectorError, LectorService
from Lector.ui import style as S
from Lector.ui.common import polish
from Lector.ui.workers import TaskRunner
from shared.fit_to_screen import fit_to_screen

WINDOW_TITLE = config.GUI_TITLE
NAV = (("searches", "Saved searches"), ("review", "Reading list"),
       ("records", "Extracted records"), ("export", "Exports"))


class LectorWindow(QMainWindow):
    def __init__(self, service=None, quiet=False):
        super().__init__()
        self.svc = service or LectorService()
        self.quiet = quiet            # tests: messages are logged, questions answered
        self.messages, self.answers = [], []
        self.tasks = TaskRunner(self)
        self._close_after_task = False
        self.setWindowTitle(WINDOW_TITLE)
        self.setStyleSheet(S.app_qss())
        self._build()
        self.resize(1440, 900)
        self.setMinimumSize(900, 560)
        fit_to_screen(self)
        self.tasks.started.connect(self._task_started)
        self.tasks.progressed.connect(self._task_progress)
        self.tasks.finished.connect(self._task_finished)

    # --- layout -------------------------------------------------------------
    def _build(self):
        from Lector.ui.builder import BuilderScreen
        from Lector.ui.export_screen import ExportScreen
        from Lector.ui.history import HistoryScreen
        from Lector.ui.review_screen import ReviewScreen
        from Lector.ui.searches import SearchesScreen
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._nav())
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.stack = QStackedWidget()
        self.screens = {
            "searches": SearchesScreen(self), "builder": BuilderScreen(self),
            "history": HistoryScreen(self), "review": ReviewScreen(self),
            "records": self._records_screen(), "export": ExportScreen(self)}
        for w in self.screens.values():
            self.stack.addWidget(w)
        right.addWidget(self.stack, 1)
        right.addWidget(self._task_bar())
        lay.addLayout(right, 1)
        self.setCentralWidget(root)

    def _nav(self):
        nav = QFrame()
        nav.setObjectName("lectorNav")
        nav.setStyleSheet(S.nav_qss())
        nav.setFixedWidth(196)
        v = QVBoxLayout(nav)
        v.setContentsMargins(0, 22, 0, 16)
        v.setSpacing(2)
        title = S.label("Lector", "h1")
        sub = S.label("Biodiversity Heritage Library reader", "small", wrap=True)
        for w in (title, sub):
            w.setContentsMargins(16, 0, 12, 0)
            v.addWidget(w)
        v.addSpacing(18)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for key, text in NAV:
            b = S.button(text, "link")
            b.setStyleSheet("")                     # the nav stylesheet styles these
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            v.addWidget(b)
        for b in self.nav_buttons.values():
            polish(b)
        widest = max(b.sizeHint().width() for b in self.nav_buttons.values())
        nav.setFixedWidth(min(260, max(196, widest + 8)))
        v.addStretch(1)
        self.nav_info = S.label("", "small", wrap=True)
        self.nav_info.setContentsMargins(16, 0, 12, 0)
        v.addWidget(self.nav_info)
        return nav

    def _records_screen(self):
        page = QWidget()
        page.setObjectName("lectorPage")
        v = QVBoxLayout(page)
        v.setContentsMargins(32, 28, 32, 24)
        v.addWidget(S.label("Extracted records", "h1"))
        card = S.Card("Coming later")
        card.body.addWidget(S.label(
            "Taking records from BHL pages into Observatum is not built yet. For now, "
            "when you have entered a page's record in Observatum by hand, mark the page "
            "“Record extracted” in the Reading list (key 3): it is counted on the "
            "Saved searches screen and kept in the dossier.", "body", wrap=True))
        v.addWidget(card)
        v.addStretch(1)
        return page

    def _task_bar(self):
        bar = QFrame()
        bar.setObjectName("lectorTaskBar")
        bar.setStyleSheet(f"QFrame#lectorTaskBar {{ background: {S.c('surface')};"
                          f" border-top: 1px solid {S.c('border')}; }}")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 6, 16, 6)
        self.task_label = QLabel("")
        self.task_label.setStyleSheet(f"color: {S.c('text_primary')};")
        self.task_label.setMinimumWidth(120)
        self.task_progress = QProgressBar()
        self.task_progress.setTextVisible(False)
        self.task_progress.setFixedWidth(220)
        self.task_cancel = S.button("Cancel", "cancel", slot=self.cancel_task)
        h.addWidget(self.task_label, 1)
        h.addWidget(self.task_progress)
        h.addWidget(self.task_cancel)
        self.task_bar = bar
        bar.hide()
        return bar

    # --- navigation ---------------------------------------------------------
    def go(self, key, **kw):
        """Show a screen (refreshing it). key: searches, builder, history, review,
        records, export; kw go to the screen's open()."""
        screen = self.screens[key]
        self.stack.setCurrentWidget(screen)
        nav_key = {"builder": "searches", "history": "searches"}.get(key, key)
        self.nav_buttons[nav_key].setChecked(True)
        if hasattr(screen, "open"):
            try:
                screen.open(**kw)
            except LectorError as exc:
                self.say(str(exc), "warning")
        self._update_nav_info()
        return screen

    def current(self):
        return self.stack.currentWidget()

    def _update_nav_info(self):
        try:
            info = self.svc.settings_info()
        except Exception:  # noqa: BLE001 - only a hint at the foot of the navigation
            return
        key = "set" if info["api_key_set"] else "not set (see README)"
        self.nav_info.setText(f"BHL API key: {key}\nDatabase: {info['db_path']}")
        self.nav_info.setToolTip(info["db_path"])

    # --- start-up: database update -------------------------------------------
    def start(self):
        """Check lector.db (offer the update an older one needs), then open Saved searches.
        True; None when the update was declined; False when the database could not be
        used (the window then closes)."""
        try:
            report = self.svc.needs_update()
        except Exception as exc:  # noqa: BLE001
            self.say(f"Lector could not open its database: {exc}", "critical")
            return False
        if report is not None:
            if not self.ask(update_question(report), "Update lector.db"):
                self.say("Nothing has been changed. Lector needs the update before it can "
                         "open this database, so it will close now.", "info")
                return None
            try:
                done = self.svc.update_database()
            except Exception as exc:  # noqa: BLE001
                self.say(f"The update failed and lector.db was not changed: {exc}", "critical")
                return False
            self.say(f"lector.db updated. Backup copy: {done.get('backup')}", "info")
        self.go("searches")
        return True

    # --- messages -------------------------------------------------------------
    def say(self, text, kind="info"):
        """Show a message (logged instead when quiet)."""
        self.messages.append(text)
        if self.quiet:
            return
        box = {"warning": QMessageBox.warning, "critical": QMessageBox.critical}.get(
            kind, QMessageBox.information)
        box(self, "Lector", text)

    def ask(self, text, title="Lector"):
        """Yes/No question; when quiet the next queued answer (default No)."""
        self.messages.append(text)
        if self.quiet:
            return self.answers.pop(0) if self.answers else False
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def call(self, fn, *args, **kw):
        """Run a quick service call; a LectorError is shown and None returned."""
        try:
            return fn(*args, **kw)
        except LectorError as exc:
            self.say(str(exc), "warning")
            return None

    # --- background tasks -----------------------------------------------------
    def run_task(self, label, fn, *args, on_done=None, on_error=None, **kw):
        """Start a background task (one at a time). False if one is running."""
        if self.tasks.busy:
            self.say(f"Wait for “{self.tasks.label}” to finish, or cancel it.", "info")
            return False
        on_error = on_error or (lambda m: self.say(m, "warning"))
        return self.tasks.start(label, fn, *args, on_done=on_done, on_error=on_error, **kw)

    def cancel_task(self):
        if self.tasks.busy:
            self.tasks.cancel()
            self.task_label.setText(f"{self.tasks.label}: stopping…")
            self.task_cancel.setEnabled(False)

    def _task_started(self, label):
        self.task_label.setText(label)
        self.task_progress.setRange(0, 0)
        self.task_cancel.setEnabled(True)
        self.task_bar.show()

    def _task_progress(self, stage, done, total, message):
        if self.tasks.cancelling:
            return
        if total:
            self.task_progress.setRange(0, total)
            self.task_progress.setValue(done)
        self.task_label.setText(f"{self.tasks.label}: {message}" if message else self.tasks.label)

    def _task_finished(self):
        self.task_bar.hide()
        if self._close_after_task:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        """A running task is cancelled first; the window closes when it has stopped."""
        if self.tasks.busy:
            self._close_after_task = True
            self.cancel_task()
            event.ignore()
            return
        screen = self.screens.get("review")
        if screen is not None:
            screen.save_notes()
        event.accept()


def update_question(report):
    """The dry-run report of the lector.db update, as a question."""
    before, after = report.get("before", {}), report.get("after", {})
    lines = ["This lector.db was made by an older Lector and needs an update.",
             "What the update would do (dry run, nothing changed yet):", ""]
    for table in sorted(set(before) | set(after)):
        b, a = before.get(table), after.get(table)
        if b != a:
            lines.append(f"  {table}: {b if b is not None else '-'} -> {a}")
    made = report.get("searches_made") or []
    if made:
        lines.append("")
        lines.append(f"Saved searches made from earlier fetches: {len(made)}")
        for s in made[:8]:
            lines.append(f"  {s['name']}: {s['pages']} pages ({', '.join(s['names'])})")
    lines += ["", "A backup copy of lector.db is made first. Update now?"]
    return "\n".join(lines)


def main(argv=None):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    win = LectorWindow()
    win.show()
    ok = win.start()
    if not ok:
        return 0 if ok is None else 1
    win.raise_()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
