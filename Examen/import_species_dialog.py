"""
Examen - Import Species Dialog

Paste species names or load from CSV/Excel. Resolves against UKSI
to produce a TVK list for PantheonAnalysisService.analyse().

Names are matched with the import wizards' rules (shared/species_lookup.py, SRCH5/EXA8,
9 Oct 2026): exact UKSI names and synonyms, cf./agg./s.l., a species before its s.l./agg.
twin. A genus name, a name held more than once, or a name not found is listed as "needs
choice" with the closest UKSI names -- never made specific silently (it was: Lotus became
a beetle, Nomada became N. alboguttata).
"""

import csv
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QComboBox,
)
from PySide6.QtGui import QFont, QColor
import paths
from shared.db_open import connect_ro  # D9: reference data, read-only
from shared.species_lookup import LookupFailure, lookup_names, search_candidates, tidy

# Ranks an analysis can take as they are; anything else (a genus, a family) needs a choice
ANALYSABLE_RANKS = ("Species", "Subspecies", "Variety", "Form", "Microspecies",
                    "Species aggregate", "Species sensu lato", "Species group")
CHOOSE = "\u2014 choose \u2014"


def unique_names(lines) -> tuple:
    """(names, duplicates dropped): blank lines out, spaces tidied, the first spelling of each
    name kept (case-insensitive)."""
    seen, names = set(), []
    for line in lines:
        n = tidy(line)
        if n and n.casefold() not in seen:
            seen.add(n.casefold())
            names.append(n)
    dropped = sum(1 for line in lines if tidy(line)) - len(names)
    return names, dropped


def resolve_names(names, uksi) -> list:
    """[{input, name, tvk, common, family, status, note, choices}] -- status 'matched',
    'needs choice' or 'not found'. choices: candidate taxa (dicts) for the user to pick."""
    found = lookup_names(names, uksi)
    out = []
    for n in names:
        r = found.get(n)
        row = {"input": n, "name": "", "tvk": "", "common": "", "family": "",
               "status": "not found", "note": "", "choices": []}
        if isinstance(r, LookupFailure) or r is None:
            cands = r.candidates if r is not None else []
            row["choices"] = [c.as_dict() for c in cands]
            if r is not None and r.kind == "ambiguous":
                row["status"], row["note"] = "needs choice", "held more than once in UKSI"
            elif r is not None and r.kind == "error":
                row["note"] = f"lookup failed: {r.message}"
            elif cands:
                row["status"], row["note"] = "needs choice", "not an exact UKSI name"
            out.append(row)
            continue
        t = r.taxon
        if (t.rank or "") not in ANALYSABLE_RANKS:
            row["status"], row["note"] = "needs choice", f"{t.rank or 'not a species'} name"
            row["choices"] = [c.as_dict() for c in search_candidates(uksi, r.looked_up, 15)
                              if c.tvk != t.tvk and (c.rank or "") in ANALYSABLE_RANKS]
            out.append(row)
            continue
        row.update({"name": t.scientific_name or "", "tvk": t.tvk or "",
                    "common": t.common_name or "", "family": t.family or "",
                    "status": "matched",
                    "note": "; ".join(r.warnings + [x for x in r.notes if not x.startswith("Imported as")])})
        out.append(row)
    return out

SURFACE = "#ffffff"
BG = "#f5f5f4"
TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"
SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"
ACCENT = "#7c6c9f"
ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"
WARM_GRAY = "#8b8178"


class ImportSpeciesDialog(QDialog):
    """Paste or import species names, resolve to TVKs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Species List")
        self.setMinimumSize(700, 560)
        self._resolved: list[dict] = []  # [{name, tvk, common, family, matched}]
        self._setup_ui()

    def get_results(self) -> tuple[list[str], dict[str, str]]:
        """Return (tvk_list, {tvk: species_name}) for resolved species -- each TVK once,
        however many input names led to it."""
        names = {}
        for r in self._resolved:
            if r["tvk"] and r["tvk"] not in names:
                names[r["tvk"]] = r["name"]
        return list(names), names

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Import species list for analysis")
        header.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: " + ACCENT_DARK + ";")
        layout.addWidget(header)
        info = QLabel("Paste species names (one per line) or load from a CSV file. "
                       "Names are matched against UKSI to resolve TVKs.")
        info.setWordWrap(True)
        info.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px;")
        layout.addWidget(info)

        # Input area
        input_row = QHBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste species names here, one per line...\n\n"
                                          "e.g.\nLucanus cervus\nBombus terrestris\nRutpela maculata")
        self.text_edit.setStyleSheet(
            "QTextEdit { border: 1px solid " + BORDER + "; border-radius: 4px; "
            "font-size: 12px; padding: 6px; }")
        self.text_edit.setMaximumHeight(160)
        input_row.addWidget(self.text_edit, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        load_btn = QPushButton("Load CSV...")
        load_btn.setStyleSheet(
            "QPushButton { background: " + ACCENT + "; color: white; border: none; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: " + ACCENT_DARK + "; }")
        load_btn.clicked.connect(self._on_load_csv)
        btn_col.addWidget(load_btn)
        resolve_btn = QPushButton("Resolve Names")
        resolve_btn.setStyleSheet(
            "QPushButton { background: " + MOSS_GREEN + "; color: white; border: none; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: #3d6a4b; }")
        resolve_btn.clicked.connect(self._on_resolve)
        btn_col.addWidget(resolve_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(
            "QPushButton { color: " + WARM_GRAY + "; border: 1px solid " + WARM_GRAY + "; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: #f0eeec; }")
        clear_btn.clicked.connect(self._on_clear)
        btn_col.addWidget(clear_btn)
        btn_col.addStretch()
        input_row.addLayout(btn_col)
        layout.addLayout(input_row)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Input Name", "Matched Name", "TVK", "Common Name",
                                              "Family", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; }")
        layout.addWidget(self.table, 1)

        # Status + buttons
        bottom = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        bottom.addWidget(self.status_label)
        bottom.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { color: " + WARM_GRAY + "; border: 1px solid " + WARM_GRAY + "; "
            "padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #f0eeec; }")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        self.use_btn = QPushButton("Use for Analysis")
        self.use_btn.setEnabled(False)
        self.use_btn.setStyleSheet(
            "QPushButton { background: " + MOSS_GREEN + "; color: white; border: none; "
            "padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #3d6a4b; }"
            "QPushButton:disabled { background: #d1d5db; color: #9ca3af; }")
        self.use_btn.clicked.connect(self.accept)
        bottom.addWidget(self.use_btn)
        layout.addLayout(bottom)

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load species list", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as f:      # a BOM is not part of the name
                reader = csv.reader(f)
                names = []
                for row in reader:
                    if not row:
                        continue
                    # Use first column, skip header-like rows
                    val = row[0].strip()
                    if val and val.lower() not in ("species", "species_name", "scientific_name", "name"):
                        names.append(val)
            self.text_edit.setPlainText("\n".join(names))
            self.status_label.setText(f"Loaded {len(names)} names from {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Examen", f"Error reading file:\n{e}")

    def _on_resolve(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        names, self._dropped = unique_names(text.splitlines())
        if not names:
            return
        self._resolved = self._resolve_names(names)
        self._refresh_table()

    def _on_clear(self):
        self.text_edit.clear()
        self._resolved.clear()
        self.table.setRowCount(0)
        self.use_btn.setEnabled(False)
        self.status_label.setText("")

    def _resolve_names(self, names: list[str]) -> list[dict]:
        """Match input names against UKSI (shared rules). Returns list of result dicts."""
        if not paths.UKSI_DB.exists():
            QMessageBox.warning(self, "Examen", "UKSI database not found.")
            return []
        conn = connect_ro(str(paths.UKSI_DB))
        try:
            return resolve_names(names, conn)
        finally:
            conn.close()

    def _refresh_table(self):
        self.table.setRowCount(len(self._resolved))
        for i, r in enumerate(self._resolved):
            self.table.setItem(i, 0, QTableWidgetItem(r["input"]))
            self.table.removeCellWidget(i, 1)
            if r["status"] == "matched":
                self.table.setItem(i, 1, QTableWidgetItem(r["name"]))
            elif r["choices"]:
                combo = QComboBox()
                combo.addItem(CHOOSE, None)
                for c in r["choices"]:
                    label = c["scientific_name"] or ""
                    if c.get("rank") and c["rank"] != "Species":
                        label += f" [{c['rank']}]"
                    elif c.get("qualifier"):
                        label += f" [{c['qualifier']}]"
                    if c.get("common_name"):
                        label += f" \u2014 {c['common_name']}"
                    combo.addItem(label, c)
                combo.currentIndexChanged.connect(lambda _ix, row=i, cb=combo: self._on_choice(row, cb))
                self.table.setItem(i, 1, QTableWidgetItem(""))
                self.table.setCellWidget(i, 1, combo)
            else:
                item = QTableWidgetItem("NOT FOUND")
                item.setForeground(QColor(RED_STATUS))
                self.table.setItem(i, 1, item)
            self.table.setItem(i, 2, QTableWidgetItem(r["tvk"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["common"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["family"]))
            note = QTableWidgetItem(r["note"] if r["status"] == "matched" else
                                    f"{r['status'].upper()}: {r['note']}".rstrip(": "))
            if r["status"] != "matched" and not r["tvk"]:
                note.setForeground(QColor(RED_STATUS))
            self.table.setItem(i, 5, note)
        self._update_status()

    def _on_choice(self, row: int, combo: QComboBox):
        """The user picked a taxon for a 'needs choice' name (or went back to none)."""
        c = combo.currentData()
        r = self._resolved[row]
        r["tvk"] = c["tvk"] if c else ""
        r["name"] = c["scientific_name"] if c else ""
        r["common"] = (c.get("common_name") or "") if c else ""
        r["family"] = (c.get("family") or "") if c else ""
        self.table.setItem(row, 2, QTableWidgetItem(r["tvk"]))
        self.table.setItem(row, 3, QTableWidgetItem(r["common"]))
        self.table.setItem(row, 4, QTableWidgetItem(r["family"]))
        self._update_status()

    def _update_status(self):
        total = len(self._resolved)
        matched = sum(1 for r in self._resolved if r["status"] == "matched")
        chosen = sum(1 for r in self._resolved if r["status"] != "matched" and r["tvk"])
        waiting = sum(1 for r in self._resolved if r["status"] == "needs choice" and not r["tvk"])
        missing = sum(1 for r in self._resolved if r["status"] == "not found" and not r["tvk"])
        species = len({r["tvk"] for r in self._resolved if r["tvk"]})
        parts = [f"{matched} matched"]
        if chosen:
            parts.append(f"{chosen} chosen by you")
        if waiting:
            parts.append(f"{waiting} need a choice (not used until chosen)")
        if missing:
            parts.append(f"{missing} not found")
        text = ", ".join(parts) + f" of {total} names \u2192 {species} species"
        if getattr(self, "_dropped", 0):
            text += f" ({self._dropped} repeated name(s) ignored)"
        self.status_label.setText(text)
        self.use_btn.setEnabled(species > 0)
