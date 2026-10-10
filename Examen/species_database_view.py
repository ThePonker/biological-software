"""
Examen - Species Database View

Browse and search species. Uses CodexRepository for conservation
status and PantheonRepository for ecology data. UKSI searched
directly for autocomplete. Manual entry editor for adding statuses
from published reviews. Naturalist theme.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSplitter, QListWidget, QListWidgetItem,
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
    "threat_iucn_2001": "GB Red List (2001 IUCN)",
    "threat_iucn_2001_breeding": "GB Red List (breeding)",
    "threat_iucn_2001_nonbreeding": "GB Red List (non-breeding)",
    "threat_iucn_legacy": "GB Red List (pre-2001)",
    "threat_global_iucn": "Global Red List",
    "rarity_modern": "GB Rarity",
    "rarity_legacy": "GB Rarity (legacy)",
    "bocc": "Birds of Conservation Concern",
    "specialist_panel": "Specialist panel",
    "red_list_england": "England Red List",
    "red_list_wales": "Wales Red List",
    "legal_protection": "Legal protection",
    "priority": "Priority listing",
}

# Single-entry tracks, in display order.
SINGLE_TRACKS = [
    "threat_iucn_2001", "threat_iucn_2001_breeding", "threat_iucn_2001_nonbreeding",
    "threat_iucn_legacy", "threat_global_iucn",
    "rarity_modern", "rarity_legacy",
    "bocc", "specialist_panel",
    "red_list_england", "red_list_wales",
]

# Tracks carrying a list of entries -- a species can hold several.
LIST_TRACKS = ["legal_protection", "priority"]

SEVERE = {"CR", "EN", "VU", "NR", "RDB1", "RDB2", "RE", "EX", "EW"}
MODERATE = {"NT", "NS", "Na", "Nb", "RDB3", "RDBK", "Notable", "DD", "Amber"}



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

        # A Codex or Pantheon read that failed says so (EXA19): an empty profile
        # must not pass for "no status, no ecology".
        self.read_error_label = QLabel("")
        self.read_error_label.setStyleSheet("color: " + RED_STATUS + "; font-size: 11px;")
        self.read_error_label.setWordWrap(True)
        self.pl.addWidget(self.read_error_label)
        self.read_error_label.hide()

        # Conservation status
        self.status_group = self._make_group("Conservation status")
        self.status_grid = QGridLayout()
        self.status_grid.setSpacing(6)
        self.status_group.layout().addLayout(self.status_grid)
        # "+ Add Manual Entry" removed (Oct 2026): its dialog emptied codex.db manual_entries,
        # which now holds every review status. Statuses come from review loads and the
        # withdraw / clear tools (scripts/), never from here. The dialog was retired 9 Oct (I8).
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
        for name, tvk, common, family, rank, note in results:
            display = f"{name}  ({common})" if common else name
            if rank and rank != "Species":
                display += f"  [{rank}]"
            if note:
                display += f"  \u2014 {note}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, (name, tvk, common, family, rank))
            if rank and rank != "Species": item.setForeground(QColor(TEXT_MUTED))
            self.results_list.addItem(item)

    def _search_uksi(self, query):
        """The suite's shared species search (SRCH19/EXA18, 10 Oct 2026): every word, typing
        slips, old names (-> the current taxon), common names, aggregates; all ranks.
        [(name, tvk, common, family, rank, note)]."""
        if not paths.UKSI_DB.exists(): return []
        from shared.species_search import search
        out = []
        for r in search(query, limit=100, db_path=str(paths.UKSI_DB)):
            note = (f"old name: {r['old_name']}" if r.get("old_name")
                    else "close spelling" if r.get("match_type") == "fuzzy" else "")
            out.append((r["scientific_name"], r["tvk"], r.get("common_name") or "",
                        r.get("family") or "", r.get("rank") or "", note))
        return out

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
        self._read_errors = []
        self._display_codex_status(tvk)
        self._display_pantheon_ecology(tvk)
        self.read_error_label.setText("\n".join(self._read_errors))
        self.read_error_label.setVisible(bool(self._read_errors))

    def _display_codex_status(self, tvk):
        while self.status_grid.count():
            w = self.status_grid.takeAt(0).widget()
            if w: w.deleteLater()
        if not tvk:
            self.status_group.hide(); self.sqs_label.setText(""); return
        try: status = self._codex.get_status_summary(tvk)
        except Exception as e:  # noqa: BLE001 -- missing or unreadable codex.db: say so
            self.status_group.hide(); self.sqs_label.setText("")
            getattr(self, "_read_errors", []).append(f"\u26a0 Codex could not be read: {e}")
            return

        # Build (track, value, detail, source) rows from the 11-track model.
        # Single-entry tracks hold an Optional[StatusEntry]; list tracks hold
        # a list of them, so a species can show several priority listings.
        rows = []
        for track in SINGLE_TRACKS:
            entry = getattr(status, track, None)
            if entry is not None and getattr(entry, "value", ""):
                rows.append((track, entry.value,
                             getattr(entry, "detail", "") or "",
                             getattr(entry, "source", "") or ""))
        for track in LIST_TRACKS:
            for entry in getattr(status, track, None) or []:
                if getattr(entry, "value", ""):
                    rows.append((track, entry.value,
                                 getattr(entry, "detail", "") or "",
                                 getattr(entry, "source", "") or ""))

        if rows:
            self.status_group.show()
            for i, (track, val, detail, source) in enumerate(rows):
                tl = QLabel(TRACK_LABELS.get(track, track))
                tl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                self.status_grid.addWidget(tl, i, 0)
                # Detail carries the instrument or jurisdiction, which is the
                # useful part for legal_protection and priority.
                shown = f"{val} \u2014 {detail}" if detail and detail != val else val
                vl = QLabel(shown)
                vl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                c = RED_STATUS if val in SEVERE else (AMBER if val in MODERATE else ACCENT_DARK)
                vl.setStyleSheet("color: " + c + "; border: none;")
                vl.setWordWrap(True)
                self.status_grid.addWidget(vl, i, 1)
                sl = QLabel(source)
                sl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 10px; border: none;")
                sl.setWordWrap(True)
                self.status_grid.addWidget(sl, i, 2)
        else: self.status_group.hide()
        if getattr(status, "status_note", ""):
            # Not the species' own: held by its sensu-lato / aggregate counterpart.
            nl = QLabel(f"({status.status_note}: {status.status_from_tvk})")
            nl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 10px; border: none;")
            self.status_grid.addWidget(nl, len(rows), 0, 1, 3)
        if status.sqs:
            # A score Pantheon does not publish, derived from current status by its
            # rule, says so -- as in the workbook (EXA7).
            derived = " (derived)" if getattr(status, "sqs_derived", False) else ""
            self.sqs_label.setText(f"Species Quality Score (SQS): {status.sqs}{derived}")
            self.sqs_label.setStyleSheet("font-size: 12px; color: " + ACCENT_DARK + "; font-weight: bold;")
        else: self.sqs_label.setText("")

    def _display_pantheon_ecology(self, tvk):
        for gl in (self.eco_layout, self.assoc_layout):
            while gl.count() > 1:
                w = gl.takeAt(1).widget()
                if w: w.deleteLater()
        if not tvk: self.ecology_group.hide(); self.assoc_group.hide(); return
        try: profile = self._pantheon.get_species_profile(tvk)
        except Exception as e:  # noqa: BLE001 -- missing or unreadable pantheon.db: say so
            self.ecology_group.hide(); self.assoc_group.hide()
            getattr(self, "_read_errors", []).append(f"\u26a0 Pantheon could not be read: {e}")
            return
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

