"""Import tab -- import a new species status review from CSV.

v2: aligned to Codex v5 / 11-track scheme. Mirrors the logic of
scripts/import_codex_review.py (intentional duplication for in-process
UX, not a shared codepath -- keep both in sync against the design spec).
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QGroupBox, QFormLayout, QTextEdit
)
from PySide6.QtCore import Signal

from . import theme


# 11-track scheme (Codex Strategy doc, section 3)
VALID_TRACKS = [
    "threat_iucn_2001",
    "threat_iucn_legacy",
    "threat_global_iucn",
    "rarity_modern",
    "rarity_legacy",
    "bocc",
    "specialist_panel",
    "legal_protection",
    "priority",
    "red_list_england",
    "red_list_wales",
]


class ImportTab(QWidget):
    """Import a review CSV into Codex."""

    import_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._csv_path = None
        self._preview_data = None
        self._setup_ui()

    # ============================================================
    # UI
    # ============================================================
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Step 1: File selection
        file_group = QGroupBox("1. Select CSV File")
        file_group.setStyleSheet(self._group_style())
        fl = QHBoxLayout(file_group)
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        fl.addWidget(self.file_label, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(self._btn_style())
        browse_btn.clicked.connect(self._browse_file)
        fl.addWidget(browse_btn)
        layout.addWidget(file_group)

        # Step 2: Review metadata
        meta_group = QGroupBox("2. Review Metadata")
        meta_group.setStyleSheet(self._group_style())
        form = QFormLayout(meta_group)
        form.setSpacing(8)
        form.setContentsMargins(12, 16, 12, 12)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. GB Macro-moth Red List")
        form.addRow("Review name:", self.name_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("e.g. Fox, Parsons & Harrower, 2019")
        form.addRow("Author(s):", self.author_edit)

        self.group_edit = QLineEdit()
        self.group_edit.setPlaceholderText("e.g. Lepidoptera")
        form.addRow("Taxon group:", self.group_edit)

        # Track combo, organised by conceptual category
        self.track_combo = QComboBox()
        self.track_combo.addItem(
            "-- Threat assessments (IUCN-criteria) --", None
        )
        self.track_combo.addItem(
            "GB Red List, IUCN 2001 (CR / EN / VU / NT / LC ...)",
            "threat_iucn_2001"
        )
        self.track_combo.addItem(
            "GB Red List, legacy (RDB1 / RDB2 / RDB3 / RDBK)",
            "threat_iucn_legacy"
        )
        self.track_combo.addItem(
            "Global Red List", "threat_global_iucn"
        )
        self.track_combo.addItem("-- Rarity (hectad-based) --", None)
        self.track_combo.addItem("GB Rarity (NR / NS)", "rarity_modern")
        self.track_combo.addItem("GB Rarity, legacy (Na / Nb / Notable)", "rarity_legacy")
        self.track_combo.addItem("-- Specialist panels --", None)
        self.track_combo.addItem("BoCC (bird Red / Amber)", "bocc")
        self.track_combo.addItem("Specialist panel (Spider Amber, etc.)", "specialist_panel")
        self.track_combo.addItem("-- Regional --", None)
        self.track_combo.addItem("England Red List", "red_list_england")
        self.track_combo.addItem("Wales Red List", "red_list_wales")
        self.track_combo.addItem("-- Legal & priority --", None)
        self.track_combo.addItem(
            "Legal Protection (WCA / Habitats / Bern / CITES / etc.)",
            "legal_protection"
        )
        self.track_combo.addItem(
            "Priority (BAP / S.41 / SBL / Welsh S7 / NI)",
            "priority"
        )
        # Set default to threat_iucn_2001
        self.track_combo.setCurrentIndex(1)
        # Disable the separator items so they can't be selected
        for i in range(self.track_combo.count()):
            if self.track_combo.itemData(i) is None:
                # Make separator items non-selectable
                self.track_combo.model().item(i).setEnabled(False)
        form.addRow("What does this\nreview assess?", self.track_combo)

        # Optional default detail
        self.detail_edit = QLineEdit()
        self.detail_edit.setPlaceholderText(
            "Optional. E.g. 'Breeding' for a bird breeding-population review"
        )
        form.addRow("Default status_detail:", self.detail_edit)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.date_edit.setText(datetime.now().strftime("%Y-%m-%d"))
        form.addRow("Date published:", self.date_edit)

        layout.addWidget(meta_group)

        # Step 3: Preview & Import
        preview_group = QGroupBox("3. Preview & Import")
        preview_group.setStyleSheet(self._group_style())
        pl = QVBoxLayout(preview_group)

        btn_row = QHBoxLayout()
        self.preview_btn = QPushButton("Preview Import")
        self.preview_btn.setStyleSheet(self._btn_style())
        self.preview_btn.clicked.connect(self._run_preview)
        self.preview_btn.setEnabled(False)
        btn_row.addWidget(self.preview_btn)

        self.import_btn = QPushButton("Import into Codex")
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.ACCENT};
                color: white;
                border: none;
                border-radius: {theme.RADIUS_SM};
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {theme.ACCENT_DARK}; }}
            QPushButton:disabled {{
                background-color: {theme.BORDER};
                color: {theme.TEXT_SECONDARY};
            }}
        """)
        self.import_btn.clicked.connect(self._run_import)
        btn_row.addWidget(self.import_btn)
        btn_row.addStretch()
        pl.addLayout(btn_row)

        # Activity log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_SM};
                padding: 8px;
            }}
        """)
        self.log.setPlaceholderText(
            "Click 'Preview Import' to see what will happen..."
        )
        pl.addWidget(self.log, 1)

        # Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels([
            "Species", "New Status", "Detail", "Action", "Current Status"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {theme.BORDER};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {theme.SURFACE_ALT};
                border: none;
                border-bottom: 1px solid {theme.BORDER};
                padding: 6px;
                font-weight: 600;
                font-size: 11px;
            }}
        """)
        pl.addWidget(self.preview_table)
        layout.addWidget(preview_group, 1)

        layout.addStretch()

    # ============================================================
    # Logging
    # ============================================================
    def _log(self, msg, colour=None):
        if colour:
            self.log.append(f'<span style="color:{colour}">{msg}</span>')
        else:
            self.log.append(msg)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    # ============================================================
    # File picker
    # ============================================================
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Review CSV", "data/reviews",
            "CSV files (*.csv);;All files (*)"
        )
        if path:
            self._csv_path = Path(path)
            self.file_label.setText(str(self._csv_path))
            self.file_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
            self.preview_btn.setEnabled(True)
            self.import_btn.setEnabled(False)
            self.log.clear()
            self.preview_table.setRowCount(0)

    # ============================================================
    # Preview
    # ============================================================
    def _run_preview(self):
        if not self._csv_path or not self._csv_path.exists():
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing", "Please enter a review name.")
            return

        track = self.track_combo.currentData()
        if track is None:
            QMessageBox.warning(self, "Missing",
                                "Please select a status track.")
            return

        self.log.clear()
        self.preview_table.setRowCount(0)
        self.import_btn.setEnabled(False)

        try:
            # Step 1: read CSV
            self._log(f"Reading CSV: {self._csv_path.name}")
            entries, has_profile_col = self._read_csv()
            if not entries:
                self._log("No valid entries found in CSV.", "#ff6b6b")
                return
            self._log(f"  Found {len(entries)} entries with species + status values")
            if has_profile_col:
                with_profile = sum(1 for e in entries if e["profile"])
                self._log(f"  Profile column detected: {with_profile} entries "
                          f"have profile text", "#4caf50")

            # Step 2: resolve species against UKSI
            self._log("")
            self._log("Resolving species names against UKSI taxonomy database...")
            resolved, unresolved = self._resolve_species(entries)
            self._log(f"  Matched: {len(resolved)} species", "#4caf50")
            if unresolved:
                self._log(f"  Unresolved: {len(unresolved)} species "
                          f"(not found in UKSI)", "#ff9800")
                for entry in unresolved[:5]:
                    self._log(f"    - {entry['name']}", "#ff9800")
                if len(unresolved) > 5:
                    self._log(f"    ... and {len(unresolved) - 5} more", "#ff9800")

            # Step 3: classify against existing Codex data
            track_label = self.track_combo.currentText()
            self._log("")
            self._log(f"Comparing against existing Codex data (track: {track_label})...")
            new, updated, unchanged = self._classify_entries(resolved, track)
            self._log(f"  New entries (species not in Codex for this track): "
                      f"{len(new)}", "#4caf50" if new else None)
            self._log(f"  Updates (status will change): "
                      f"{len(updated)}", "#ff9800" if updated else None)
            self._log(f"  Unchanged (already has this status): {len(unchanged)}")

            if updated:
                self._log("")
                self._log("Changes:")
                for entry in updated[:10]:
                    self._log(f"  {entry['resolved_name']}: "
                              f"{entry.get('current_value', '?')} -> {entry['value']}",
                              "#ff9800")
                if len(updated) > 10:
                    self._log(f"  ... and {len(updated) - 10} more")

            # Profile classification
            profile_new = profile_updated = profile_unchanged = 0
            if has_profile_col:
                profile_new, profile_updated, profile_unchanged = (
                    self._classify_profiles(resolved)
                )
                self._log("")
                self._log("Species profiles:")
                self._log(f"  New profile entries: {profile_new}",
                          "#4caf50" if profile_new else None)
                self._log(f"  Profile updates: {profile_updated}",
                          "#ff9800" if profile_updated else None)
                self._log(f"  Unchanged: {profile_unchanged}")

            self._preview_data = {
                "resolved": resolved,
                "unresolved": unresolved,
                "new": new,
                "updated": updated,
                "unchanged": unchanged,
                "has_profile_col": has_profile_col,
                "profile_new": profile_new,
                "profile_updated": profile_updated,
            }

            # Summary
            total_status = len(new) + len(updated)
            total_profile = profile_new + profile_updated
            self._log("")
            if total_status > 0 or total_profile > 0:
                self._log("Ready to import:", "#4caf50")
                if total_status:
                    self._log(f"  {total_status} status entries", "#4caf50")
                if total_profile:
                    self._log(f"  {total_profile} species profiles", "#4caf50")
                self._log("")
                self._log("Storage:")
                self._log("  - manual_entries (status overrides, with review link)")
                self._log("  - status_summary (live status surface)")
                self._log("  - reviews (registers this as review "
                          f"#{self._next_review_id()})")
                if has_profile_col and total_profile:
                    self._log("  - species_profiles (descriptive paragraphs)")
                self._log("")
                self._log("Click 'Import into Codex' to proceed, "
                          "or change settings and preview again.")
            else:
                self._log("Nothing to import -- all species already have "
                          "this status in Codex.", "#78909c")

            # Populate preview table
            show = new + updated
            self.preview_table.setRowCount(min(len(show), 50))
            for i, entry in enumerate(show[:50]):
                self.preview_table.setItem(i, 0, QTableWidgetItem(
                    entry["resolved_name"]))
                self.preview_table.setItem(i, 1, QTableWidgetItem(entry["value"]))
                self.preview_table.setItem(i, 2, QTableWidgetItem(entry["detail"] or ""))
                action = "NEW" if entry in new else "UPDATE"
                self.preview_table.setItem(i, 3, QTableWidgetItem(action))
                self.preview_table.setItem(i, 4, QTableWidgetItem(
                    entry.get("current_value", "")))

            if total_status > 0 or total_profile > 0:
                self.import_btn.setEnabled(True)

        except Exception as e:
            self._log(f"Error: {e}", "#ff6b6b")

    # ============================================================
    # Import
    # ============================================================
    def _run_import(self):
        if not self._preview_data:
            return

        total_status = (len(self._preview_data['new']) +
                        len(self._preview_data['updated']))
        total_profile = (self._preview_data.get('profile_new', 0) +
                         self._preview_data.get('profile_updated', 0))

        msg = f"Import {total_status} status entries"
        if total_profile:
            msg += f" and {total_profile} species profiles"
        msg += " into Codex?\n\nThis writes to codex.db and cannot be undone."

        reply = QMessageBox.question(
            self, "Confirm Import", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        import paths
        try:
            self._log("")
            self._log("=" * 50)
            self._log("IMPORTING INTO CODEX", "#4caf50")
            self._log("=" * 50)

            codex = sqlite3.connect(str(paths.CODEX_DB))
            c = codex.cursor()
            now = datetime.now().isoformat()
            track = self.track_combo.currentData()
            source = f"{self.name_edit.text()} ({self.author_edit.text()})"

            # Register review
            self._log(f"Registering review in reviews table...")
            c.execute("""INSERT INTO reviews
                (review_name, author, taxon_group, status_track, date_published,
                 date_imported, source_file, species_count, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.name_edit.text(), self.author_edit.text(),
                 self.group_edit.text(), track, self.date_edit.text(),
                 now, str(self._csv_path.name),
                 len(self._preview_data["resolved"]),
                 "Imported via Codex Manager"))
            review_id = c.lastrowid
            self._log(f"  Review #{review_id} registered", "#4caf50")

            # Status entries
            all_entries = self._preview_data["new"] + self._preview_data["updated"]
            self._log(f"Writing {len(all_entries)} status entries...")
            for entry in all_entries:
                tvk = entry["resolved_tvk"]
                name = entry["resolved_name"]
                value = entry["value"]
                detail = entry["detail"]
                notes = entry.get("notes", "")
                iucn = entry.get("iucn_version", "")

                c.execute("""INSERT INTO manual_entries
                    (tvk, species_name, status_track, status_value, status_detail,
                     source_review, date_added, added_by, notes, review_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tvk, name, track, value, detail,
                     source, now, "review-import", notes, review_id))

                c.execute("""INSERT OR REPLACE INTO status_summary
                    (tvk, status_track, status_value, status_detail,
                     source, iucn_version, date_designated, origin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')""",
                    (tvk, track, value, detail, source, iucn, self.date_edit.text()))
            self._log(f"  {len(all_entries)} status entries written", "#4caf50")

            # Species profiles
            profile_writes = 0
            if self._preview_data["has_profile_col"]:
                self._log("Writing species profiles...")
                for entry in self._preview_data["resolved"]:
                    text = entry["profile"]
                    if not text:
                        continue
                    tvk = entry["resolved_tvk"]
                    c.execute("SELECT 1 FROM species_profiles WHERE tvk = ?", (tvk,))
                    if c.fetchone():
                        c.execute("""UPDATE species_profiles
                                     SET profile_text = ?, source = ?,
                                         date_updated = ?, added_by = 'review-import'
                                     WHERE tvk = ?""",
                                  (text, source, now, tvk))
                    else:
                        c.execute("""INSERT INTO species_profiles
                            (tvk, profile_text, source, date_added,
                             date_updated, added_by)
                            VALUES (?, ?, ?, ?, NULL, 'review-import')""",
                            (tvk, text, source, now))
                    profile_writes += 1
                self._log(f"  {profile_writes} species profiles written", "#4caf50")

            codex.commit()
            codex.close()

            # Save unresolved
            if self._preview_data["unresolved"]:
                unres_path = self._csv_path.parent / "unresolved_species.csv"
                self._append_unresolved(unres_path, self._preview_data["unresolved"])
                self._log(f"  {len(self._preview_data['unresolved'])} unresolved species "
                          f"logged to {unres_path.name}", "#ff9800")

            self._log("")
            self._log("IMPORT COMPLETE", "#4caf50")
            self._log(f"  Review #{review_id}: {self.name_edit.text()}")
            self._log(f"  {len(all_entries)} status entries")
            if profile_writes:
                self._log(f"  {profile_writes} species profiles")
            self._log("")
            self._log("Run seed_codex.py to refresh derived SQS scores.",
                      "#78909c")

            self.import_btn.setEnabled(False)
            self._preview_data = None
            self.import_completed.emit()

        except Exception as e:
            self._log(f"IMPORT ERROR: {e}", "#ff6b6b")
            QMessageBox.critical(self, "Import Error", str(e))

    # ============================================================
    # CSV reading
    # ============================================================
    def _read_csv(self):
        """Returns (entries, has_profile_col)."""
        entries = []
        with open(self._csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            self._log(f"  Columns found: {', '.join(headers)}")

            name_col = next((h for h in headers if h.lower() in
                             ("species_name", "species", "taxon",
                              "scientific_name", "name")), None)
            value_col = next((h for h in headers if h.lower() in
                              ("status_value", "status", "category",
                               "red_list", "rarity", "value")), None)
            tvk_col = next((h for h in headers if h.lower() in
                            ("tvk", "taxonversionkey")), None)
            notes_col = next((h for h in headers if h.lower() in
                              ("notes", "criteria", "comment")), None)
            iucn_col = next((h for h in headers if h.lower() in
                             ("iucn_version", "iucn", "criteria_version")), None)
            detail_col = next((h for h in headers if h.lower() in
                               ("detail", "status_detail", "specifier")), None)
            profile_col = next((h for h in headers if h.lower() in
                                ("profile_text", "profile", "ecology",
                                 "description", "habitat_notes")), None)

            if not name_col or not value_col:
                raise ValueError(
                    f"CSV must have species_name and status_value columns. "
                    f"Found: {headers}"
                )

            self._log(f"  Using: species='{name_col}', status='{value_col}'"
                      f"{f', tvk={tvk_col}' if tvk_col else ''}"
                      f"{f', detail={detail_col}' if detail_col else ''}"
                      f"{f', profile={profile_col}' if profile_col else ''}")

            default_detail = self.detail_edit.text().strip() or None

            for row in reader:
                name = (row.get(name_col) or "").strip()
                value = (row.get(value_col) or "").strip()
                if not name or not value:
                    continue
                row_detail = (row.get(detail_col) or "").strip() if detail_col else ""
                entries.append({
                    "name": name,
                    "value": value,
                    "tvk": (row.get(tvk_col) or "").strip() if tvk_col else "",
                    "notes": (row.get(notes_col) or "").strip() if notes_col else "",
                    "iucn_version": (row.get(iucn_col) or "").strip() if iucn_col else "",
                    "detail": row_detail or default_detail,
                    "profile": (row.get(profile_col) or "").strip() if profile_col else "",
                })

        return entries, profile_col is not None

    def _next_review_id(self):
        try:
            import paths
            conn = sqlite3.connect(str(paths.CODEX_DB))
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM reviews"
            ).fetchone()
            conn.close()
            return row[0] if row else 1
        except Exception:
            return "?"

    # ============================================================
    # Species resolution
    # ============================================================
    def _resolve_species(self, entries):
        import paths
        uksi = sqlite3.connect(str(paths.UKSI_DB))
        resolved = []
        unresolved = []
        for entry in entries:
            tvk, name = self._resolve_one(uksi, entry["name"], entry.get("tvk"))
            if tvk:
                entry["resolved_tvk"] = tvk
                entry["resolved_name"] = name
                resolved.append(entry)
            else:
                unresolved.append(entry)
        uksi.close()
        return resolved, unresolved

    def _resolve_one(self, conn, name, tvk=None):
        if tvk:
            row = conn.execute(
                "SELECT scientific_name FROM taxa WHERE tvk = ?", (tvk,)
            ).fetchone()
            if row:
                return tvk, row[0]
        row = conn.execute(
            "SELECT tvk, scientific_name FROM taxa WHERE scientific_name = ? "
            "AND rank = 'Species' LIMIT 1", (name,)
        ).fetchone()
        if row:
            return row[0], row[1]
        row = conn.execute(
            "SELECT tvk, scientific_name FROM taxa "
            "WHERE LOWER(scientific_name) = LOWER(?) "
            "AND rank = 'Species' LIMIT 1", (name,)
        ).fetchone()
        if row:
            return row[0], row[1]
        return None, None

    # ============================================================
    # Diff against existing Codex data
    # ============================================================
    def _classify_entries(self, resolved, track):
        """Compare against existing status_summary, partitioned by
        (tvk, track, detail) for primary-key consistency."""
        import paths
        codex = sqlite3.connect(str(paths.CODEX_DB))
        new, updated, unchanged = [], [], []
        for entry in resolved:
            detail = entry["detail"] or ""
            row = codex.execute(
                "SELECT status_value FROM status_summary "
                "WHERE tvk = ? AND status_track = ? "
                "  AND COALESCE(status_detail, '') = ?",
                (entry["resolved_tvk"], track, detail)
            ).fetchone()
            if row:
                entry["current_value"] = row[0]
                if row[0] == entry["value"]:
                    unchanged.append(entry)
                else:
                    updated.append(entry)
            else:
                entry["current_value"] = ""
                new.append(entry)
        codex.close()
        return new, updated, unchanged

    def _classify_profiles(self, resolved):
        """Diff profile text against existing species_profiles."""
        import paths
        codex = sqlite3.connect(str(paths.CODEX_DB))
        new = updated = unchanged = 0
        for entry in resolved:
            text = entry["profile"]
            if not text:
                continue
            row = codex.execute(
                "SELECT profile_text FROM species_profiles WHERE tvk = ?",
                (entry["resolved_tvk"],)
            ).fetchone()
            if row:
                if row[0] == text:
                    unchanged += 1
                else:
                    updated += 1
            else:
                new += 1
        codex.close()
        return new, updated, unchanged

    # ============================================================
    # Unresolved log
    # ============================================================
    def _append_unresolved(self, path, unresolved):
        exists = path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow([
                    "species_name", "review", "phase", "iucn_status",
                    "reason", "notes"
                ])
            review_name = self.name_edit.text()
            for entry in unresolved:
                writer.writerow([
                    entry["name"], review_name, "",
                    entry["value"], "Not in UKSI", ""
                ])

    # ============================================================
    # Styles
    # ============================================================
    def _group_style(self):
        return f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 12px;
                color: {theme.ACCENT};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_MD};
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
        """

    def _btn_style(self):
        return f"""
            QPushButton {{
                padding: 6px 16px;
                border: 1px solid {theme.ACCENT};
                border-radius: {theme.RADIUS_SM};
                color: {theme.ACCENT};
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.ACCENT_LIGHT};
            }}
            QPushButton:disabled {{
                border-color: {theme.BORDER};
                color: {theme.TEXT_SECONDARY};
            }}
        """
