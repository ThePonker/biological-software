"""
Examen - Manual Entry Dialog

Add/edit conservation statuses from published reviews not yet in JNCC.
Dual storage: writes to data/codex_manual_entries.json (portable) AND
applies immediately to codex.db manual_entries table (live effect).
"""

import json
import sqlite3
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import paths

# Naturalist palette
SURFACE = "#ffffff"
BG = "#f5f5f4"
TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"
SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"
ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"
WARM_GRAY = "#8b8178"

JSON_PATH = paths.DATA_DIR / "codex_manual_entries.json"

STATUS_TRACKS = [
    ("gb_red_list", "GB Red List", ["CR", "EN", "VU", "NT", "DD", "LC"]),
    ("gb_rarity", "GB Rarity", ["NR", "NS"]),
    ("gb_rarity_legacy", "GB Rarity (legacy)", ["Na", "Nb", "Notable"]),
    ("gb_red_list_legacy", "GB Red List (legacy)", ["RDB1", "RDB2", "RDB3", "RDBK"]),
    ("section_41", "Section 41", ["England", "Wales", "Scotland", "Northern Ireland"]),
    ("bap", "UK BAP", ["UK"]),
    ("legal_protection", "Legal protection", ["WCA Sch5", "Habitats Directive", "Bern Convention"]),
]


def _load_json() -> list[dict]:
    if JSON_PATH.exists():
        try:
            return json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_json(entries: list[dict]):
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _apply_to_codex(entries: list[dict]):
    """Write manual entries to codex.db manual_entries + rebuild status_summary rows."""
    if not paths.CODEX_DB.exists():
        return
    conn = sqlite3.connect(str(paths.CODEX_DB))
    c = conn.cursor()
    # Ensure manual_entries table exists
    c.execute("""CREATE TABLE IF NOT EXISTS manual_entries (
        tvk TEXT NOT NULL, species_name TEXT, status_track TEXT NOT NULL,
        status_value TEXT NOT NULL, source TEXT DEFAULT '',
        date_added TEXT, PRIMARY KEY (tvk, status_track))""")
    c.execute("DELETE FROM manual_entries")
    for e in entries:
        c.execute("INSERT OR REPLACE INTO manual_entries VALUES (?,?,?,?,?,?)",
                  (e["tvk"], e.get("species_name", ""), e["status_track"],
                   e["status_value"], e.get("source", ""), e.get("date_added", "")))
        # Also update status_summary for immediate effect
        c.execute("INSERT OR REPLACE INTO status_summary (tvk, status_track, status_value, source, origin) "
                  "VALUES (?, ?, ?, ?, 'manual')",
                  (e["tvk"], e["status_track"], e["status_value"], e.get("source", "")))
    conn.commit()
    conn.close()


class ManualEntryDialog(QDialog):
    """Dialog for managing manual conservation status entries."""

    def __init__(self, parent=None, preselect_tvk: str = "", preselect_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Manual Conservation Entries")
        self.setMinimumSize(780, 520)
        self._entries = _load_json()
        self._preselect_tvk = preselect_tvk
        self._preselect_name = preselect_name
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Add conservation statuses from published reviews")
        header.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: " + ACCENT_DARK + ";")
        layout.addWidget(header)
        info = QLabel("These entries supplement JNCC data. They persist across Codex rebuilds "
                       "and are stored in codex_manual_entries.json.")
        info.setWordWrap(True)
        info.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px;")
        layout.addWidget(info)

        # Add entry form
        form_frame = QHBoxLayout()
        form_frame.setSpacing(6)
        self.tvk_edit = QLineEdit(self._preselect_tvk)
        self.tvk_edit.setPlaceholderText("TVK")
        self.tvk_edit.setFixedWidth(160)
        self.name_edit = QLineEdit(self._preselect_name)
        self.name_edit.setPlaceholderText("Species name")
        self.name_edit.setFixedWidth(200)
        self.track_combo = QComboBox()
        for track_id, label, _ in STATUS_TRACKS:
            self.track_combo.addItem(label, track_id)
        self.track_combo.setFixedWidth(160)
        self.track_combo.currentIndexChanged.connect(self._on_track_changed)
        self.value_combo = QComboBox()
        self.value_combo.setFixedWidth(120)
        self.value_combo.setEditable(True)
        self._on_track_changed(0)
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Source review")
        for w in (self.tvk_edit, self.name_edit, self.source_edit):
            w.setStyleSheet("padding: 4px 6px; border: 1px solid " + BORDER + "; border-radius: 3px;")
        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(
            "QPushButton { background: " + MOSS_GREEN + "; color: white; border: none; "
            "padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background: #3d6a4b; }")
        add_btn.clicked.connect(self._on_add)
        for w in [self.tvk_edit, self.name_edit, self.track_combo, self.value_combo, self.source_edit, add_btn]:
            form_frame.addWidget(w)
        layout.addLayout(form_frame)

        # Entries table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["TVK", "Species", "Track", "Value", "Source"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 12px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; }")
        layout.addWidget(self.table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet(
            "QPushButton { color: " + RED_STATUS + "; border: 1px solid " + RED_STATUS + "; "
            "padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background: #f5e6e6; }")
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()
        count_lbl = QLabel("")
        count_lbl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        self._count_label = count_lbl
        btn_row.addWidget(count_lbl)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { color: " + WARM_GRAY + "; border: 1px solid " + WARM_GRAY + "; "
            "padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background: #f0eeec; }")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _on_track_changed(self, idx):
        self.value_combo.clear()
        if 0 <= idx < len(STATUS_TRACKS):
            self.value_combo.addItems(STATUS_TRACKS[idx][2])

    def _on_add(self):
        tvk = self.tvk_edit.text().strip()
        name = self.name_edit.text().strip()
        track = self.track_combo.currentData()
        value = self.value_combo.currentText().strip()
        source = self.source_edit.text().strip()
        if not tvk or not value:
            QMessageBox.warning(self, "Examen", "TVK and status value are required.")
            return
        # Check for duplicate tvk+track
        for e in self._entries:
            if e["tvk"] == tvk and e["status_track"] == track:
                e["status_value"] = value
                e["source"] = source
                e["species_name"] = name
                self._save_and_refresh()
                return
        self._entries.append({"tvk": tvk, "species_name": name, "status_track": track,
                              "status_value": value, "source": source,
                              "date_added": date.today().isoformat()})
        self._save_and_refresh()

    def _on_delete(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not rows:
            return
        for r in rows:
            if 0 <= r < len(self._entries):
                self._entries.pop(r)
        self._save_and_refresh()

    def _save_and_refresh(self):
        _save_json(self._entries)
        _apply_to_codex(self._entries)
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._entries))
        for i, e in enumerate(self._entries):
            self.table.setItem(i, 0, QTableWidgetItem(e.get("tvk", "")))
            self.table.setItem(i, 1, QTableWidgetItem(e.get("species_name", "")))
            track_label = dict((t[0], t[1]) for t in STATUS_TRACKS).get(e.get("status_track", ""), e.get("status_track", ""))
            self.table.setItem(i, 2, QTableWidgetItem(track_label))
            self.table.setItem(i, 3, QTableWidgetItem(e.get("status_value", "")))
            self.table.setItem(i, 4, QTableWidgetItem(e.get("source", "")))
        self._count_label.setText(f"{len(self._entries)} manual entries")
