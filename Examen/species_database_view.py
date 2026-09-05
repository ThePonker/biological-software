"""
Examen - Species Database View

Browse and search species. Uses CodexRepository for conservation
status and PantheonRepository for ecology data. UKSI searched
directly for autocomplete. Manual entry editor for adding statuses
from published reviews. Naturalist theme.
"""

import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSplitter, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
import paths

BG = "#f5f5f4"
SURFACE = "#ffffff"
TEXT_PRIMARY = "#1f2937"
TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"
SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"
ACCENT = "#7c6c9f"
ACCENT_LIGHT = "#f0edf5"
ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"
AMBER = "#c2956e"

TRACK_LABELS = {
    "gb_red_list": "GB Red List", "gb_red_list_legacy": "GB Red List (legacy)",
    "gb_rarity": "GB Rarity", "gb_rarity_legacy": "GB Rarity (legacy)",
    "section_41": "Section 41", "bap": "UK BAP",
    "legal_protection": "Legal protection", "global_red_list": "Global Red List",
}
SEVERE = {"CR", "EN", "VU", "NR", "RDB1", "RDB2"}
MODERATE = {"NT", "NS", "Na", "Nb", "RDB3", "RDBK", "Notable"}


class SpeciesDatabaseView(QWidget):

    def __init__(self, codex_repo, pantheon_repo):
        super().__init__()
        self._codex = codex_repo
        self._pantheon = pantheon_repo
        self._current_tvk = ""
        self._current_name = ""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search bar
        sf = QFrame()
        sf.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                         + BORDER + "; border-radius: 6px; padding: 8px; }")
        sl = QHBoxLayout(sf)
        sl.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel("Search species:")
        lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 12px; border: none;")
        sl.addWidget(lbl)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a species name (minimum 3 characters)...")
        self.search_input.setStyleSheet(
            "QLineEdit { padding: 6px 8px; border: 1px solid " + BORDER + "; border-radius: 4px; "
            "font-size: 12px; color: " + TEXT_PRIMARY + "; background: " + SURFACE + "; }"
            "QLineEdit:focus { border-color: " + ACCENT + "; }")
        self.search_input.textChanged.connect(self._on_search_changed)
        sl.addWidget(self.search_input, 1)
        layout.addWidget(sf)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: results
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.result_count = QLabel("")
        self.result_count.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        ll.addWidget(self.result_count)
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(
            "QListWidget { border: 1px solid " + BORDER + "; border-radius: 4px; "
            "background: " + SURFACE + "; font-size: 12px; }"
            "QListWidget::item { padding: 6px 10px; border-bottom: 1px solid " + SEPARATOR + "; }"
            "QListWidget::item:selected { background-color: " + ACCENT_LIGHT + "; color: " + ACCENT_DARK + "; }"
            "QListWidget::item:hover:!selected { background: #f9fafb; }")
        self.results_list.currentItemChanged.connect(self._on_species_selected)
        ll.addWidget(self.results_list, 1)
        splitter.addWidget(left)

        # Right: profile
        rs = QScrollArea()
        rs.setWidgetResizable(True)
        rs.setStyleSheet("QScrollArea { border: none; background: " + BG + "; }")
        self.profile_widget = QWidget()
        self.profile_widget.setStyleSheet("background: " + BG + ";")
        self.pl = QVBoxLayout(self.profile_widget)
        self.pl.setContentsMargins(16, 16, 16, 16)
        self.pl.setSpacing(12)

        self.species_name_label = QLabel("Select a species to view its profile")
        self.species_name_label.setFont(QFont("Georgia", 15, QFont.Weight.Bold))
        self.species_name_label.setStyleSheet("color: " + ACCENT_DARK + ";")
        self.species_name_label.setWordWrap(True)
        self.pl.addWidget(self.species_name_label)
        self.common_name_label = QLabel("")
        self.common_name_label.setFont(QFont("Segoe UI", 11))
        self.common_name_label.setStyleSheet("color: " + TEXT_SECONDARY + ";")
        self.pl.addWidget(self.common_name_label)
        self.tvk_label = QLabel("")
        self.tvk_label.setStyleSheet("font-family: monospace; color: " + TEXT_MUTED + "; font-size: 11px;")
        self.pl.addWidget(self.tvk_label)

        # Conservation status
        self.status_group = self._make_group("Conservation status")
        self.status_grid = QGridLayout()
        self.status_grid.setSpacing(6)
        self.status_group.layout().addLayout(self.status_grid)
        # Manual entry button inside status group
        self.manual_btn = QPushButton("+ Add Manual Entry")
        self.manual_btn.setStyleSheet(
            "QPushButton { color: " + ACCENT + "; border: 1px solid " + ACCENT + "; "
            "padding: 4px 12px; border-radius: 3px; font-size: 11px; background: none; }"
            "QPushButton:hover { background: " + ACCENT_LIGHT + "; }")
        self.manual_btn.clicked.connect(self._on_manual_entry)
        self.status_group.layout().addWidget(self.manual_btn)
        self.pl.addWidget(self.status_group)
        self.status_group.hide()

        self.sqs_label = QLabel("")
        self.sqs_label.setStyleSheet("font-size: 12px;")
        self.pl.addWidget(self.sqs_label)

        self.ecology_group = self._make_group("Ecology (Pantheon)")
        self.eco_layout = self.ecology_group.layout()
        self.pl.addWidget(self.ecology_group)
        self.ecology_group.hide()

        self.assoc_group = self._make_group("Associations")
        self.assoc_layout = self.assoc_group.layout()
        self.pl.addWidget(self.assoc_group)
        self.assoc_group.hide()

        self.pl.addStretch()
        rs.setWidget(self.profile_widget)
        splitter.addWidget(rs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    def _make_group(self, title):
        g = QFrame()
        g.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid " + BORDER + "; border-radius: 6px; }")
        v = QVBoxLayout(g)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        h = QLabel(title)
        h.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        h.setStyleSheet("color: " + ACCENT_DARK + "; border: none; padding-bottom: 4px; border-bottom: 2px solid " + ACCENT_LIGHT + ";")
        v.addWidget(h)
        return g

    # ── Search ───────────────────────────────────────────────────
    def _on_search_changed(self, text): self._search_timer.start()

    def _do_search(self):
        q = self.search_input.text().strip()
        self.results_list.clear()
        if len(q) < 3:
            self.result_count.setText("")
            return
        results = self._search_uksi(q)
        self.result_count.setText(f"{len(results)} species found")
        for name, tvk, common, family, rank in results:
            display = f"{name}  ({common})" if common else name
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, (name, tvk, common, family, rank))
            if rank and rank != "Species": item.setForeground(QColor(TEXT_MUTED))
            self.results_list.addItem(item)

    def _search_uksi(self, query):
        if not paths.UKSI_DB.exists(): return []
        conn = sqlite3.connect(str(paths.UKSI_DB))
        c = conn.cursor()
        c.execute("""SELECT t.scientific_name, t.tvk, cn.common_name, t.family, t.rank
            FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk AND cn.preferred = 1
            WHERE t.scientific_name LIKE ? AND t.rank IN ('Species','Subspecies')
            ORDER BY t.sort_code LIMIT 100""", (f"%{query}%",))
        r = c.fetchall()
        conn.close()
        return r

    # ── Profile ──────────────────────────────────────────────────
    def _on_species_selected(self, current, prev):
        if not current: return
        data = current.data(Qt.ItemDataRole.UserRole)
        if not data: return
        name, tvk, common, family, rank = data
        self._current_tvk, self._current_name = tvk, name
        self.species_name_label.setText(name)
        self.common_name_label.setText(f"{common}  \u2014  {family}" if common else family or "")
        self.tvk_label.setText(f"TVK: {tvk}" if tvk else "")
        self._display_codex_status(tvk)
        self._display_pantheon_ecology(tvk)

    def _display_codex_status(self, tvk):
        while self.status_grid.count():
            w = self.status_grid.takeAt(0).widget()
            if w: w.deleteLater()
        if not tvk:
            self.status_group.hide(); self.sqs_label.setText(""); return
        try: status = self._codex.get_status_summary(tvk)
        except FileNotFoundError: self.status_group.hide(); self.sqs_label.setText(""); return
        rows = []
        for track, attr, src in [
                ("gb_red_list","gb_red_list","gb_red_list_source"),("gb_red_list_legacy","gb_red_list_legacy","gb_red_list_legacy_source"),
                ("gb_rarity","gb_rarity","gb_rarity_source"),("gb_rarity_legacy","gb_rarity_legacy","gb_rarity_legacy_source"),
                ("section_41","section_41",None),("bap","bap",None),("legal_protection","legal_protection",None),("global_red_list","global_red_list",None)]:
            v = getattr(status, attr, "")
            if v: rows.append((track, v, getattr(status, src, "") if src else ""))
        if rows:
            self.status_group.show()
            for i, (track, val, source) in enumerate(rows):
                tl = QLabel(TRACK_LABELS.get(track, track))
                tl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                self.status_grid.addWidget(tl, i, 0)
                vl = QLabel(val)
                vl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                c = RED_STATUS if val in SEVERE else (AMBER if val in MODERATE else ACCENT_DARK)
                vl.setStyleSheet("color: " + c + "; border: none;")
                self.status_grid.addWidget(vl, i, 1)
                sl = QLabel(source)
                sl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 10px; border: none;")
                self.status_grid.addWidget(sl, i, 2)
        else: self.status_group.hide()
        if status.sqs:
            self.sqs_label.setText(f"Species Quality Score (SQS): {status.sqs}")
            self.sqs_label.setStyleSheet("font-size: 12px; color: " + ACCENT_DARK + "; font-weight: bold;")
        else: self.sqs_label.setText("")

    def _display_pantheon_ecology(self, tvk):
        for gl in (self.eco_layout, self.assoc_layout):
            while gl.count() > 1:
                w = gl.takeAt(1).widget()
                if w: w.deleteLater()
        if not tvk: self.ecology_group.hide(); self.assoc_group.hide(); return
        try: profile = self._pantheon.get_species_profile(tvk)
        except FileNotFoundError: self.ecology_group.hide(); self.assoc_group.hide(); return
        if not profile: self.ecology_group.hide(); self.assoc_group.hide(); return
        has = False
        for label, val in [("Broad biotope", ", ".join(profile.broad_biotopes) if profile.broad_biotopes else ""),
                           ("Habitats", ", ".join(profile.habitats) if profile.habitats else ""),
                           ("Larval guild", profile.larval_guild), ("Adult guild", profile.adult_guild),
                           ("SATs", ", ".join(profile.sats) if profile.sats else ""),
                           ("Fidelity", ", ".join(f"{k}: {v}" for k,v in profile.fidelity_scores.items()) if profile.fidelity_scores else "")]:
            if val: has = True; self._eco_row(label, val)
        self.ecology_group.setVisible(has)
        if profile.associations:
            self.assoc_group.show()
            for atype, taxon in profile.associations[:10]:
                al = QLabel(f"{atype}: {taxon}")
                al.setStyleSheet("font-size: 11px; border: none; color: " + TEXT_PRIMARY + ";")
                al.setWordWrap(True)
                self.assoc_layout.addWidget(al)
            if len(profile.associations) > 10:
                self.assoc_layout.addWidget(QLabel(f"... and {len(profile.associations)-10} more"))
        else: self.assoc_group.hide()

    def _eco_row(self, label, value):
        w = QWidget(); w.setStyleSheet("border: none;"); r = QHBoxLayout(w)
        l = QLabel(f"{label}:"); l.setStyleSheet("color: "+TEXT_SECONDARY+"; font-size: 11px; border: none;"); l.setFixedWidth(110); r.addWidget(l)
        v = QLabel(value); v.setStyleSheet("font-size: 11px; border: none; color: "+TEXT_PRIMARY+";"); v.setWordWrap(True); r.addWidget(v, 1)
        self.eco_layout.addWidget(w)

    def _on_manual_entry(self):
        from .manual_entry_dialog import ManualEntryDialog
        dlg = ManualEntryDialog(self, self._current_tvk, self._current_name)
        dlg.exec()
        if self._current_tvk: self._display_codex_status(self._current_tvk)
