"""
Examen -- the right-click menu for "likely to be downgraded" marks (see status_marks).

Used on the Key Species rows of the Species tab. Every change is one explicit menu choice; a
missing table shows "Run scripts\\add_report_tables.py first" and changes nothing.
"""
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                               QLineEdit, QMenu, QMessageBox)

from Examen import status_marks as sm

ALL_JOBS = "All jobs"
THIS_JOB = "This job only"


class MarkDialog(QDialog):
    """Asks for the reason and whether the mark is for every job or this job only."""

    def __init__(self, species_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Status likely to be downgraded")
        form = QFormLayout(self)
        form.addRow(QLabel(f"{species_name}: show its status in [square brackets] and leave it "
                           "out of the revised Key Species figures."))
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Why (e.g. status out of date, review pending)")
        form.addRow("Reason:", self.reason)
        self.scope = QComboBox()
        self.scope.addItems([ALL_JOBS, THIS_JOB])
        form.addRow("Applies to:", self.scope)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def values(self):
        return self.reason.text().strip(), self.scope.currentText()


NO_CODE = "No rarity or threat status in Codex to mark"


def show_menu(parent, global_pos, tvk, name, job, on_change):
    """Offer the mark actions for one Key Species. job = (project_name, client, survey_year);
    a new mark is made against the species' Codex status (sm.current_key);
    on_change() is called after a change was written."""
    if not tvk:
        return
    project, client, year = job
    glob = sm.is_globally_marked(tvk)
    over = {o["tvk"]: o["bracket"] for o in sm.list_overrides(project, client, year)}
    mark = sm.bracket_checker(project, client, year).detail(tvk)
    bracketed = mark["bracketed"]
    stale = mark["state"] == sm.STALE
    menu = QMenu(parent)
    acts = {}
    if stale:           # the status changed since it was marked: not applied, but still saved
        acts[menu.addAction("Remove mark")] = "remove"
        acts[menu.addAction("Mark again with the current status")] = "again"
    elif not bracketed:
        try:
            has_code = bool(sm.current_key(tvk))
        except Exception:  # noqa: BLE001 -- Codex unreadable: let the mark try, and say so there
            has_code = True
        if has_code:
            acts[menu.addAction("Mark status as likely to be downgraded…")] = "mark"
        else:           # Codex holds only a priority / legal listing or LC: nothing to bracket
            menu.addAction(NO_CODE).setEnabled(False)
    else:
        acts[menu.addAction("Remove mark")] = "remove"
    if glob and tvk not in over and not stale:
        acts[menu.addAction("Don't bracket in this job")] = "unbracket"
    if glob and over.get(tvk) == 0 and mark["global_state"] != sm.STALE:
        acts[menu.addAction("Bracket in this job again")] = "rebracket"
    chosen = acts.get(menu.exec(global_pos))
    if not chosen:
        return
    try:
        if chosen == "mark":
            dlg = MarkDialog(name, parent)
            if not dlg.exec():
                return
            reason, scope = dlg.values()
            if scope == THIS_JOB:
                sm.set_override(project, client, year, tvk, name, True, sm.current_key(tvk))
            else:
                sm.set_mark(tvk, name, reason, sm.current_key(tvk))
                sm.clear_override(project, client, year, tvk)
        elif chosen == "again":
            sm.mark_again(tvk, name)
        elif chosen == "remove":
            sm.remove_mark(project, client, year, tvk)
        elif chosen == "unbracket":
            sm.set_override(project, client, year, tvk, name, False)
        elif chosen == "rebracket":
            sm.clear_override(project, client, year, tvk)
    except sm.MissingTables as e:
        QMessageBox.information(parent, "Status marks", str(e))
        return
    except Exception as e:  # noqa: BLE001 -- say so; nothing is half-written (one row per write)
        QMessageBox.warning(parent, "Status marks", f"The mark could not be saved.\n\n{e}")
        return
    on_change()
