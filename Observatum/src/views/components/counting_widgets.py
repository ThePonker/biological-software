"""Small widgets for the species-counting switches (backlog A, 10 Oct 2026).

- only_excluded_toggle(): the "Show only excluded" box on the Observation and Recording
  Scheme filter bars -- lists just the dimmed rows the switches leave out of counts.
- ask_export_mode(): what an export from a counting screen writes -- the counted records
  (default), every record, or only the excluded ones (for cleaning, answer 6 of note 38).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel,
                               QVBoxLayout, QWidget)

from shared.species_counting import (EXPORT_COUNTED, EXPORT_INCLUDE, EXPORT_LABELS,
                                     EXPORT_ONLY)

from ...themes import theme


def only_excluded_toggle(parent: Optional[QWidget] = None) -> QCheckBox:
    chk = QCheckBox("Show only excluded", parent)
    chk.setToolTip("List only the records your species-counting settings leave out of counts "
                   "(the dimmed rows), e.g. genus-only names and aggregates.\n"
                   "Change which kinds are left out in Settings > Species counting.")
    t = theme()
    chk.setStyleSheet(f"QCheckBox {{ font-size: 11px; color: {t.get('text_secondary')}; }}")
    return chk


def show_duplicates_toggle(parent: Optional[QWidget] = None) -> QCheckBox:
    """Recording Scheme: list the NBN Atlas copies of iRecord records too (dimmed, never
    counted; shared/scheme_duplicates.py, Q59). Off by default."""
    chk = QCheckBox("Show duplicates", parent)
    chk.setToolTip("Also list the NBN Atlas copies of iRecord records (the same record sent "
                   "twice).\nThey are shown dimmed with a \"Duplicate of\" column and are never "
                   "counted: the iRecord copy is the one that counts.")
    t = theme()
    chk.setStyleSheet(f"QCheckBox {{ font-size: 11px; color: {t.get('text_secondary')}; }}")
    return chk


def ask_export_mode(parent: Optional[QWidget] = None, what: str = "records") -> Optional[str]:
    """Counted / include excluded / only excluded; None if cancelled."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Export")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(f"Which {what} to export?"))
    combo = QComboBox()
    for mode in (EXPORT_COUNTED, EXPORT_INCLUDE, EXPORT_ONLY):
        combo.addItem(EXPORT_LABELS[mode], mode)
    lay.addWidget(combo)
    note = QLabel("Excluded records are the ones your Species counting settings leave out "
                  "(genus-only names, aggregates and so on).")
    note.setWordWrap(True)
    note.setStyleSheet(f"color: {theme().get('text_secondary')}; font-size: 11px;")
    lay.addWidget(note)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    lay.addWidget(buttons)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return combo.currentData()
