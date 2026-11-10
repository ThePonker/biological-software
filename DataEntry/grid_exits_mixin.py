"""The entry grid page's three exits (commit, export, discard) and their safety checks (split from entry_grid.py, R13)."""
from __future__ import annotations


from PySide6.QtWidgets import (
    QDialog, QFileDialog, QMessageBox,
)

from DataEntry import staging_repo as repo
from DataEntry.grid_columns import (
    COLUMNS, _CSV_COLUMNS)
from DataEntry.grid_dialogs import ExportOptionsDialog, EmbargoDialog

class GridExitsMixin:
    """Methods of EntryGridPage: Commit to Observatum, Export to CSV, Discard, iRecord export."""
    # -- the three exits -----------------------------------------------------
    def _is_commercial(self) -> bool:
        return (self._job.get("mode") or "").lower().startswith("comm")

    def _do_commit(self):
        from DataEntry import commit_service as cs  # noqa: F401 (kept for symmetry/tests)
        if repo.is_test_copy(self._job):
            QMessageBox.information(self, "Commit", "This is a test copy of a job: it cannot be "
                                    "committed. Discard it when you have finished with it.")
            return
        if self._commit_cb is None:
            QMessageBox.information(self, "Commit",
                                   "Commit needs Observatum \u2014 launch via run_entry.bat.")
            return
        if self._model.real_count() == 0:
            QMessageBox.information(self, "Commit", "Nothing to commit yet.")
            return
        if self._is_commercial() and not (self._job.get("project") or "").strip():
            # Without a project the records become "(no project)" in Examen and
            # Commercial Reports (8 Oct 2026). Set it with Jobs > Edit details.
            QMessageBox.warning(
                self, "Commit",
                "This commercial job has no Project, so its records would not be grouped "
                "with any project in Examen or Commercial Reports.\n\nGo back to Jobs, select "
                "this job, choose \u201cEdit details\u201d and set the Project (and Client), "
                "then reopen it and commit.")
            return
        if not self._confirm_precommit_issues(cs):
            return
        embargo = None
        if self._is_commercial():
            dlg = EmbargoDialog(self, self._job.get("embargo_until"))
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            embargo = dlg.value()
        if QMessageBox.question(
            self, "Commit to Observatum",
            "Write this job's records into Observatum? Committed rows are removed from staging.",
        ) != QMessageBox.StandardButton.Yes:
            return
        summary = None
        try:
            summary = self._commit_cb(self._job_id, embargo)
        except Exception as e:
            # commit_job reports a part-way failure in its summary; an exception here came
            # before the first record was written
            QMessageBox.warning(self, "Commit failed", f"Nothing was committed.\n\n{e}")
            return
        if summary is None:
            QMessageBox.warning(self, "Commit failed",
                                "Could not write to Observatum. Nothing was committed.")
            return
        if summary.get("error"):
            # DE4: part-way -- say how many were written, and refresh Observation Data
            n = int(summary.get("committed") or 0)
            QMessageBox.warning(
                self, "Commit stopped",
                f"Committed {n} record(s), then stopped:\n\n{summary['error']}\n\n"
                f"{summary.get('remaining', 0)} row(s) are still in staging. The {n} written are "
                f"in Observatum under {summary.get('batch')}.")
            if n:
                self.committed.emit(n)
            self.finished.emit()
            return
        bits = [f"Committed {summary['committed']} record(s)."]
        detail = []
        if summary.get("skipped_species"):
            detail.append(f"{summary['skipped_species']} skipped (no species)")
        if summary.get("skipped_date"):
            detail.append(f"{summary['skipped_date']} skipped (no date)")
        if summary.get("skipped_bad_date"):
            detail.append(f"{summary['skipped_bad_date']} skipped (date unreadable)")
        if summary.get("skipped_bad_qty"):
            detail.append(f"{summary['skipped_bad_qty']} skipped (No. unreadable)")
        if summary.get("skipped_zero_qty"):
            detail.append(f"{summary['skipped_zero_qty']} not committed (count of 0 \u2014 fix the count)")
        if summary.get("skipped_bad_vc"):
            detail.append(f"{summary['skipped_bad_vc']} skipped (VC No. unreadable)")
        if summary.get("skipped_check"):
            detail.append(f"{summary['skipped_check']} row(s) marked to check stay in Data Entry")
        if summary.get("taxonomy_error"):
            detail.append("taxon group and sort key not written (UKSI unreadable: "
                          f"{summary['taxonomy_error']})")
        if summary.get("unresolved"):
            detail.append(f"{summary['unresolved']} committed without a TVK")
        if summary.get("future"):
            detail.append(f"{summary['future']} have a future date \u2014 worth checking")
        if detail:
            bits.append("; ".join(detail))
        def listed(names, limit=10):
            return ", ".join(names[:limit]) + (f" \u2026 (+{len(names) - limit} more)"
                                              if len(names) > limit else "")
        syn = summary.get("synonyms") or []
        if syn:
            bits.append(f"\n{len(syn)} written under their current UKSI name: "
                        + listed([x.replace(" -> ", " \u2192 ") for x in syn]))
        for key, text in (("name_tvk_differ", "name is not the name of its TVK (written as entered, "
                                              "check them)"),
                          ("ambiguous_names", "ambiguous name, matches more than one UKSI taxon "
                                              "(written as entered)"),
                          ("qualified_names", "qualified name not changed to the current UKSI name "
                                              "(written as entered)")):
            if summary.get(key):
                bits.append(f"\n{len(summary[key])} {text}: {listed(summary[key])}")
        probs = summary.get("photo_problems") or []
        if probs:
            more = f"\n\u2026 and {len(probs) - 20} more" if len(probs) > 20 else ""
            bits.append("\nPhotos and specimens:\n" + "\n".join(probs[:20]) + more)
        if summary.get("remaining"):
            bits.append(f"\n{summary['remaining']} row(s) left in staging to fix \u2014 the job stays open.")
        QMessageBox.information(self, "Committed", "\n".join(bits))
        if summary.get("committed"):
            self.committed.emit(int(summary["committed"]))
        self.finished.emit()

    def _confirm_precommit_issues(self, cs) -> bool:
        """Show gaps and doubles before commit (backlog B8). True = go ahead."""
        try:
            rows = repo.fetch_rows(self._conn, self._job_id)
            try:
                names = cs.uksi_names_for_rows(rows)
            except Exception as e:      # the name/TVK check is skipped; the other checks still run
                print(f"[DataEntry] name/TVK check skipped: {e}")
                names = None
            found = cs.precommit_issues(rows, names)
        except Exception as e:  # a failed check must not block a commit silently
            print(f"[DataEntry] pre-commit check skipped: {e}")
            return True
        held = found.pop("to check (held back)", None)
        if not found:
            return True                # only rows held back on purpose: the summary says so

        def rows_text(v, limit=15):
            shown = ", ".join(str(x) for x in v[:limit])
            return shown + (f" \u2026 (+{len(v) - limit} more)" if len(v) > limit else "")

        labels = {"unreadable date": "a date that can't be read (left in staging)",
                  "count of 0": "a count of 0 \u2014 fix the count (left in staging, never committed)",
                  "unreadable No.": "a No. that can't be read (left in staging)",
                  "unreadable VC No.": "a VC No. that can't be read (left in staging)",
                  "future date": "a date in the future",
                  "no site": "no site name", "no grid ref": "no grid reference",
                  "no VC": "no vice-county", "no recorder": "no recorder",
                  "no TVK": "species not matched (no TVK)",
                  "name and TVK differ": "a species name that is not the name of its TVK "
                                         "(the species was changed and the old TVK left)"}
        lines = []
        for key in ("unreadable date", "count of 0", "unreadable No.", "unreadable VC No.", "future date", "no site",
                    "no grid ref", "no VC",
                    "no recorder", "no TVK", "name and TVK differ"):
            if key in found:
                v = found[key]
                lines.append(f"\u2022 {len(v)} with {labels[key]}: rows {rows_text(v)}")
        if "double" in found:
            pairs = [f"{a} (= {b})" for a, b in found["double"]]
            lines.append(f"\u2022 {len(pairs)} possible double entr{'y' if len(pairs) == 1 else 'ies'} "
                         f"(same species, date, grid ref, method, trap, sex and stage): rows {rows_text(pairs, 10)}")
        if held:
            lines.append(f"\u2022 {len(held)} marked to check (held back, they stay in Data Entry): "
                         f"rows {rows_text(held)}")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Check before commit")
        box.setText("Some rows would be committed with gaps or as doubles:")
        box.setInformativeText("\n".join(lines) + "\n\nRow numbers are the grid's. Doubles can be genuine "
                               "(separate lines on the sheet); gaps are easier to fix now than after commit.")
        back = box.addButton("Go back and fix", QMessageBox.ButtonRole.RejectRole)
        anyway = box.addButton("Commit anyway", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(back)
        box.exec()
        return box.clickedButton() is anyway

    def _do_export(self):
        from DataEntry import commit_service as cs
        # ask whether to clear the job afterwards (default: clear, preserving old behaviour)
        dlg = ExportOptionsDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        clear_after = dlg.clear_after()
        default = f"{(self._job.get('name') or 'job').replace(' ', '_')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export job to CSV", default, "CSV files (*.csv)")
        if not path:
            return
        if clear_after and not self._safety_copy("Export and clear"):
            return
        after = self._ask_photos("Export and clear") if clear_after else (lambda: None)
        if after is None:
            return
        try:
            if clear_after:
                n = cs.export_and_discard(self._conn, self._job, path, COLUMNS)   # keeps the To check marks
                after()
            else:
                n = cs.export_job(self._conn, self._job, path, _CSV_COLUMNS)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        if clear_after:
            QMessageBox.information(self, "Exported",
                                   f"Wrote {n} row(s) to:\n{path}\n\nThe job's staged rows have been cleared.")
            self.finished.emit()
        else:
            QMessageBox.information(self, "Exported",
                                   f"Wrote {n} row(s) to:\n{path}\n\nThe job is unchanged \u2014 still open.")
            # stay on the grid; nothing else to do

    def _do_discard(self):
        from DataEntry import commit_service as cs
        n = self._model.real_count()
        msg = "Discard this job" + (f" and its {n} staged row{'s' if n != 1 else ''}?" if n else "?")
        msg += "\n\nThis removes only staged working data \u2014 nothing already in Observatum."
        if QMessageBox.question(self, "Discard job", msg) != QMessageBox.StandardButton.Yes:
            return
        if not self._safety_copy("Discard"):
            return
        after = self._ask_photos("Discard job")
        if after is None:
            return
        cs.discard_job(self._conn, self._job)
        after()
        self.finished.emit()

    def _ask_photos(self, what: str):
        """The job's rows are about to be cleared: where do their bench photos go? None = stop,
        else call the result once the rows are gone (photo_attach.ask_about_photos)."""
        from DataEntry.photo_attach import ask_about_photos
        return ask_about_photos(self, self._conn, [r["id"] for r in repo.fetch_rows(self._conn, self._job_id)], what)

    def _safety_copy(self, what: str) -> bool:
        """Staging CSV before rows are cleared (DE8). False = stop. The hook raises when the
        kept backup of observatum.db failed (it has told Wil): then nothing is cleared."""
        try:
            if self.before_change is None or self.before_change():
                return True
        except RuntimeError:
            return False
        return QMessageBox.question(
            self, "Safety copy failed",
            f"The staging safety copy (staging_backup.csv) could not be written.\n\n{what} "
            "anyway?") == QMessageBox.StandardButton.Yes

    def _do_irecord_export(self):
        """Personal job: CSV for iRecord's import; the job waits for the records (DE7)."""
        from DataEntry.irecord_return_dialog import export_for_irecord
        if export_for_irecord(self, self._conn, repo.get_job(self._conn, self._job_id) or self._job):
            self.finished.emit()
