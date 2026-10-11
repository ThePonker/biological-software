"""
Field record box for the Add / Edit Specimen dialog (11 Oct 2026).

Shows, in plain words, the observation (field record) this specimen is linked to
(specimens.observation_id), or "Not linked". "Pick..." opens the chooser
(field_record_picker.py); "Clear" removes the link; the tick box "Checked: no field record
exists" records that Wil looked and there is none (specimens.no_field_record_checked, the
date and time ticked). A link and the tick are mutually exclusive.

Nothing is written here: changes() gives the fields to save, and the specimen dialog's
existing save path (SpecimenRepository.create / update) writes them with the rest. Only
fields that changed are returned, so a specimen whose link could not be read is never
overwritten.

Before scripts/add_specimen_link_check_column.py has run, the tick box is hidden and a
one-line hint says to run it; linking still works.
"""

import sqlite3
from datetime import datetime
from typing import Callable, Dict, Optional

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox
)

from src.utils.date_utils import format_date_display
from shared.specimen_links import CHECK_COLUMN, get_observation, has_check_column

from ...themes import theme
from ...core.config import TabColors, ButtonColors

SCRIPT_HINT = ("To mark a specimen \"checked: no field record\", run "
               "scripts\\add_specimen_link_check_column.py once (Observatum closed).")


def describe_observation(o: Optional[Dict], others: int = 0) -> str:
    """'12/06/2025, Bernwood Forest, SP580207, Heeney, W.J., quantity 2 (observation 4321)'."""
    if not o:
        return ""
    parts = [format_date_display(o.get("date") or "", "user") or "no date",
             o.get("site_name") or "no site", o.get("grid_ref") or "no grid ref",
             o.get("recorder") or "no recorder"]
    if o.get("quantity") is not None:
        parts.append(f"quantity {o['quantity']}")
    if o.get("sex") and str(o["sex"]).strip().lower() != "not recorded":
        parts.append(str(o["sex"]))
    text = ", ".join(parts) + f" (observation {o['id']})"
    if others:
        text += f"; {others} other specimen{'s' if others != 1 else ''} linked to it"
    return text


class FieldRecordBox(QFrame):
    """The 'Field record' section of the specimen dialog."""

    def __init__(self, specimen_id, db_path: str, context: Callable[[], Dict],
                 uksi_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._sid = specimen_id
        self._db_path = str(db_path)
        self._uksi_path = uksi_path
        self._context = context
        self._loaded = False
        self._has_col = False
        self._obs_id = self._orig_obs = None
        self._checked = self._orig_checked = None
        self._obs = None
        self._others = 0
        self._build()
        self._load()
        self._refresh()

    # ── UI ─────────────────────────────────────────────────────────────
    def _build(self):
        t = theme()
        accent = TabColors.COLLECTION
        self.setObjectName("fieldRecordBox")
        self.setStyleSheet(f"#fieldRecordBox {{ background-color: {t.get('surface_alt')};"
                           f" border-radius: {t.get('radius_md')}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        title = QLabel("Field record")
        title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        lay.addWidget(title)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"font-size: 12px; color: {t.get('text_primary')};")
        lay.addWidget(self.summary)

        row = QHBoxLayout()
        self.pick_btn = QPushButton("Pick…")
        self.pick_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {accent}; color: {accent};"
            f" border-radius: {t.get('radius_sm')}; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background-color: {t.get('hover')}; }}")
        self.pick_btn.clicked.connect(self._on_pick)
        row.addWidget(self.pick_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {ButtonColors.SECONDARY}; color: "
            f"{ButtonColors.SECONDARY}; border-radius: {t.get('radius_sm')}; padding: 4px 12px;"
            f" font-size: 12px; }} QPushButton:hover {{ background-color: {t.get('hover')}; }}"
            f" QPushButton:disabled {{ color: {t.get('text_muted')};"
            f" border-color: {t.get('text_muted')}; }}")
        self.clear_btn.clicked.connect(self.clear_link)
        row.addWidget(self.clear_btn)
        row.addStretch()
        lay.addLayout(row)
        for b in (self.pick_btn, self.clear_btn):
            b.setAutoDefault(False)

        self.check = QCheckBox("Checked: no field record exists")
        self.check.toggled.connect(self._on_check)
        lay.addWidget(self.check)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"font-size: 11px; color: {t.get('text_muted')};")
        lay.addWidget(self.hint)

    # ── state ──────────────────────────────────────────────────────────
    def _connect(self):
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def _load(self):
        try:
            conn = self._connect()
        except sqlite3.Error as e:
            self.summary.setText(f"Could not read the field record link: {e}")
            return
        try:
            self._has_col = has_check_column(conn)
            if self._sid:
                cols = "observation_id" + (f", {CHECK_COLUMN}" if self._has_col else "")
                r = conn.execute(f"SELECT {cols} FROM specimens WHERE id = ?",
                                 (int(self._sid),)).fetchone()
                if r:
                    self._obs_id = self._orig_obs = r[0]
                    if self._has_col:
                        self._checked = self._orig_checked = r[1] or None
            self._describe(conn)
            self._loaded = True
        except sqlite3.Error as e:
            self.summary.setText(f"Could not read the field record link: {e}")
        finally:
            conn.close()

    def _describe(self, conn):
        self._obs = get_observation(conn, self._obs_id) if self._obs_id is not None else None
        self._others = 0
        if self._obs_id is not None:
            q = "SELECT COUNT(*) FROM specimens WHERE observation_id = ?"
            args = [int(self._obs_id)]
            if self._sid:
                q += " AND id <> ?"
                args.append(int(self._sid))
            self._others = conn.execute(q, args).fetchone()[0]

    def _refresh(self):
        if not self._loaded:
            for w in (self.pick_btn, self.clear_btn, self.check):
                w.setEnabled(False)
            return
        if self._obs_id is not None:
            text = ("Linked to " + describe_observation(self._obs, self._others) if self._obs
                    else f"Linked to observation {self._obs_id}, which is no longer in the records.")
        elif self._checked:
            when = format_date_display(str(self._checked)[:10], "user")
            text = f"Not linked: checked, no field record exists (marked {when})."
        else:
            text = "Not linked."
        if self.is_changed():
            text += "  (Saved when you save the specimen.)"
        self.summary.setText(text)
        self.clear_btn.setEnabled(self._obs_id is not None)
        self.check.blockSignals(True)
        self.check.setChecked(bool(self._checked))
        self.check.blockSignals(False)
        self.check.setVisible(self._has_col)
        self.hint.setText("" if self._has_col else SCRIPT_HINT)
        self.hint.setVisible(not self._has_col)

    # ── actions ────────────────────────────────────────────────────────
    def _on_pick(self):
        from .field_record_picker import FieldRecordPicker
        spec = dict(self._context() or {})
        spec["id"] = self._sid
        dlg = FieldRecordPicker(spec, self._db_path, self._uksi_path, self._obs_id, self)
        if dlg.exec() and dlg.chosen():
            self.set_link(dlg.chosen()["id"])

    def set_link(self, obs_id):
        """Link to this observation (clears the 'checked, none' mark)."""
        self._obs_id = int(obs_id) if obs_id is not None else None
        if self._obs_id is not None:
            self._checked = None
        try:
            conn = self._connect()
            try:
                self._describe(conn)
            finally:
                conn.close()
        except sqlite3.Error:
            self._obs = None
        self._refresh()

    def clear_link(self):
        self.set_link(None)

    def _on_check(self, on: bool):
        if on:
            self._checked = (self._orig_checked if self._orig_checked and self._orig_obs is None
                             else datetime.now().isoformat(timespec="seconds"))
            self._obs_id, self._obs, self._others = None, None, 0
        else:
            self._checked = None
        self._refresh()

    # ── for the dialog's save ──────────────────────────────────────────
    def is_changed(self) -> bool:
        return self._loaded and (self._obs_id != self._orig_obs
                                 or (self._has_col and self._checked != self._orig_checked))

    def changes(self) -> Dict:
        """The specimen fields to save: only those that changed."""
        out: Dict = {}
        if not self._loaded:
            return out
        if self._obs_id != self._orig_obs:
            out["observation_id"] = self._obs_id
        if self._has_col and self._checked != self._orig_checked:
            out[CHECK_COLUMN] = self._checked
        return out
