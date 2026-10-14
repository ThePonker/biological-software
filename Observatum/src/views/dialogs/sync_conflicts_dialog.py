"""Sync conflicts -- records changed both here and in iRecord since the last sync (A2,
14 Oct 2026). Nothing was written for them; Wil chooses per record:

  Keep Observatum's  -- the record stays as edited here; correct iRecord by hand (Open in
                        iRecord). The next sync keeps it until iRecord's copy changes again.
  Take iRecord's     -- iRecord's values are written for the fields that differ.

Closing without Apply writes nothing: the same records are listed at the next sync.
The rule and the writes are shared/sync_conflicts.py.
"""
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from shared import sync_conflicts as sc

from ...core.config import ButtonColors
from ...themes import theme

KEEP_OBS, TAKE_IREC = "Keep Observatum's", "Take iRecord's"


class SyncConflictsDialog(QDialog):
    def __init__(self, conflicts: list, db, parent=None):
        super().__init__(parent)
        self.conflicts = conflicts
        self.db = db
        self.applied = 0
        self.setWindowTitle("Changed here and in iRecord")
        self.resize(980, 520)
        t = theme()
        root = QVBoxLayout(self)
        intro = QLabel(
            f"{len(conflicts)} record(s) were edited here and have also changed in iRecord since "
            "the last sync. Nothing has been written for them. Choose which version to keep.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 13px;")
        root.addWidget(intro)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Record", "Field", "Observatum", "iRecord", "Keep"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        for c in range(4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.choices = []
        for c in conflicts:
            first = self.table.rowCount()
            for f in c["fields"]:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(
                    f"{c.get('species') or ''} (id {c['id']})" if r == first else ""))
                self.table.setItem(r, 1, QTableWidgetItem(sc.LABELS.get(f, f)))
                self.table.setItem(r, 2, QTableWidgetItem(str(c["observatum"].get(f) or "")))
                self.table.setItem(r, 3, QTableWidgetItem(str(c["irecord"].get(f) or "")))
            box = QComboBox()
            box.addItems([KEEP_OBS, TAKE_IREC])
            self.table.setCellWidget(first, 4, box)
            if len(c["fields"]) > 1:
                self.table.setSpan(first, 4, len(c["fields"]), 1)
            self.choices.append(box)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.addStretch()
        later = QPushButton("Decide later")
        later.setStyleSheet(f"QPushButton {{ background: transparent; color: {ButtonColors.SECONDARY}; "
                            f"border: 1px solid {ButtonColors.SECONDARY}; border-radius: {t.get('radius_md')}; "
                            "padding: 8px 20px; }")
        later.clicked.connect(self.reject)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(f"QPushButton {{ background: {ButtonColors.PRIMARY}; color: white; border: none; "
                                f"border-radius: {t.get('radius_md')}; padding: 8px 24px; }}")
        apply_btn.clicked.connect(self._apply)
        row.addWidget(later)
        row.addWidget(apply_btn)
        root.addLayout(row)

    def chosen(self) -> list:
        """[(conflict, 'observatum' | 'irecord')] as currently set."""
        return [(c, "irecord" if b.currentText() == TAKE_IREC else "observatum")
                for c, b in zip(self.conflicts, self.choices)]

    def _apply(self):
        taken = []
        with self.db.main_connection() as conn:
            for c, choice in self.chosen():
                incoming = dict(c.get("incoming_all") or c["irecord"],
                                last_edited_date=c["last_edited_date"])
                sc.resolve(conn, c["id"], choice, incoming, c["fields"])
                if choice == "irecord" and "species_name" in c["fields"]:
                    taken.append((c["id"], c["observatum"].get("species_name"),
                                  c["irecord"].get("species_name")))
            conn.commit()
        # iRecord's species taken: the record's linked photos follow (B5)
        from shared.photo_files import follow_redet
        for rid, old, new in taken:
            if old and new:
                follow_redet(self.db, "observation", rid, old, new)
        self.applied = len(self.conflicts)
        self.accept()
