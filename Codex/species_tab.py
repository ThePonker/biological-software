"""Species tab -- search species and view all conservation statuses.

v2: aligned to Codex v5 / 11-track scheme.
"""

import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFrame,
    QScrollArea, QPushButton
)
from PySide6.QtCore import Qt, QTimer

from . import theme


# ============================================================
# Display order + labels for the 11-track scheme
# ============================================================
# Tuple: (track_key, label, sublabel)
# Order matters -- this is how cards are rendered top to bottom.
# ============================================================
TRACK_DISPLAY_ORDER = [
    ("threat_iucn_2001",       "GB Red List",                "IUCN 2001 guidelines"),
    ("threat_iucn_2001_breeding",
                                "GB Red List (Breeding)",     "IUCN 2001, breeding population"),
    ("threat_iucn_2001_nonbreeding",
                                "GB Red List (Non-breeding)", "IUCN 2001, non-breeding population"),
    ("threat_iucn_legacy",     "GB Red List (Legacy)",       "Pre-2001 IUCN / RDB"),
    ("threat_global_iucn",     "Global Red List",            "IUCN global assessment"),

    ("rarity_modern",          "GB Rarity",                  "Current NR/NS hectad-based"),
    ("rarity_legacy",          "GB Rarity (Legacy)",         "Na / Nb / Notable"),

    ("bocc",                   "BoCC",                       "Birds of Conservation Concern"),
    ("specialist_panel",       "Specialist Panel",           "Non-IUCN expert listings"),

    ("red_list_england",       "England Red List",           "Country-specific assessment"),
    ("red_list_wales",         "Wales Red List",             "Country-specific assessment"),

    ("priority",               "Priority Listings",          "BAP / S.41 / SBL / Welsh S7 / NI Priority"),
    ("legal_protection",       "Legal Protection",           "WCA / Habitats / Bern / CITES / etc."),
]


class SpeciesTab(QWidget):
    """Search and view species conservation profiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._do_search)
        self._setup_ui()

    # ============================================================
    # UI scaffolding
    # ============================================================
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a species name...")
        self.search_input.setMinimumHeight(36)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {theme.BORDER};
                border-radius: {theme.RADIUS_MD};
                padding: 6px 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {theme.ACCENT};
            }}
        """)
        self.search_input.textChanged.connect(lambda: self._debounce.start())
        search_row.addWidget(self.search_input, 1)
        layout.addLayout(search_row)

        # Search results (clickable list)
        self.results_frame = QFrame()
        self.results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_SM};
            }}
        """)
        self.results_frame.hide()
        self.results_layout = QVBoxLayout(self.results_frame)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(0)
        layout.addWidget(self.results_frame)

        # Species profile (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_layout.setSpacing(12)
        self.profile_layout.addStretch()
        scroll.setWidget(self.profile_container)
        layout.addWidget(scroll, 1)

    # ============================================================
    # Search (UKSI lookup, debounced)
    # ============================================================
    def _do_search(self):
        text = self.search_input.text().strip()
        self._clear_results()
        if len(text) < 2:
            self.results_frame.hide()
            return

        try:
            import paths
            conn = sqlite3.connect(str(paths.UKSI_DB))

            words = text.lower().split()

            common_join_query = (
                "SELECT DISTINCT t.tvk, t.scientific_name, "
                "  (SELECT c2.common_name FROM common_names c2 "
                "   WHERE c2.tvk = t.tvk ORDER BY c2.preferred DESC LIMIT 1) AS common_name "
                "FROM taxa t "
                "LEFT JOIN common_names c ON t.tvk = c.tvk "
                "WHERE t.rank = 'Species' "
            )

            if len(words) == 1:
                term = f"%{words[0]}%"
                rows = conn.execute(
                    common_join_query +
                    "AND (LOWER(t.scientific_name) LIKE ? "
                    "     OR LOWER(c.common_name) LIKE ?) "
                    "ORDER BY CASE "
                    "  WHEN LOWER(t.scientific_name) LIKE ? THEN 0 "
                    "  ELSE 1 END, "
                    "t.scientific_name "
                    "LIMIT 15",
                    (term, term, f"{words[0]}%")
                ).fetchall()
            else:
                conditions = []
                params = []
                for w in words:
                    conditions.append(
                        "(LOWER(t.scientific_name || ' ' || COALESCE(c.common_name, '')) LIKE ?)"
                    )
                    params.append(f"%{w}%")
                where = " AND ".join(conditions)
                rows = conn.execute(
                    common_join_query +
                    f"AND {where} "
                    f"ORDER BY t.scientific_name LIMIT 15",
                    params
                ).fetchall()

            conn.close()
        except Exception as e:
            self.results_frame.show()
            err = QLabel(f"Search error: {e}")
            err.setStyleSheet("color: red; padding: 8px;")
            self.results_layout.addWidget(err)
            return

        if not rows:
            self.results_frame.show()
            no_results = QLabel("No matching species found")
            no_results.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; padding: 10px; font-style: italic;"
            )
            self.results_layout.addWidget(no_results)
            return

        self.results_frame.show()
        for tvk, sci_name, common in rows:
            item = self._make_result_item(tvk, sci_name, common or "")
            self.results_layout.addWidget(item)

    def _make_result_item(self, tvk, sci_name, common):
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                border-bottom: 1px solid {theme.SEPARATOR};
            }}
            QFrame:hover {{
                background-color: {theme.ACCENT_LIGHT};
            }}
        """)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        il = QHBoxLayout(item)
        il.setContentsMargins(10, 6, 10, 6)

        name_lbl = QLabel(f"<i>{sci_name}</i>")
        name_lbl.setStyleSheet(f"font-weight: 600; color: {theme.TEXT_PRIMARY};")
        il.addWidget(name_lbl)

        if common:
            common_lbl = QLabel(common)
            common_lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
            il.addWidget(common_lbl)

        il.addStretch()
        item.mousePressEvent = lambda e, t=tvk, s=sci_name: self._select_species(t, s)
        return item

    def _select_species(self, tvk, sci_name):
        self.results_frame.hide()
        self._debounce.stop()
        self.search_input.blockSignals(True)
        self.search_input.setText(sci_name)
        self.search_input.blockSignals(False)
        self._show_profile(tvk, sci_name)

    # ============================================================
    # Profile display
    # ============================================================
    def _show_profile(self, tvk, sci_name):
        self._clear_profile()

        try:
            from shared.repositories.codex_repository import CodexRepository
            repo = CodexRepository()
            summary = repo.get_species_conservation_summary(tvk)
            repo.close()
        except Exception as e:
            err = QLabel(f"Error loading profile: {e}")
            err.setStyleSheet("color: red; padding: 12px;")
            self.profile_layout.insertWidget(0, err)
            return

        idx = 0

        # ----- Header card -----
        header_card = self._make_header_card(sci_name, summary)
        self.profile_layout.insertWidget(idx, header_card)
        idx += 1

        # ----- Species profile paragraph (if present) -----
        profile_text = summary.get("profile")
        if profile_text:
            profile_card = self._make_profile_card(
                profile_text, summary.get("profile_source") or ""
            )
            self.profile_layout.insertWidget(idx, profile_card)
            idx += 1

        # ----- Track cards (only populated tracks) -----
        any_track = False
        for track_key, label, sublabel in TRACK_DISPLAY_ORDER:
            entries = self._get_track_entries(summary, track_key)
            if not entries:
                continue
            any_track = True
            card = self._make_track_card(label, sublabel, entries)
            self.profile_layout.insertWidget(idx, card)
            idx += 1

        if not any_track:
            empty = QLabel("No conservation status recorded for this species in Codex.")
            empty.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; padding: 16px; "
                f"font-style: italic; font-size: 13px;"
            )
            self.profile_layout.insertWidget(idx, empty)
            idx += 1

    # ----------------------------------------------------------
    # Helpers: header card, profile card, track card
    # ----------------------------------------------------------
    def _make_header_card(self, sci_name, summary):
        card = QFrame()
        card.setObjectName("headerCard")
        card.setStyleSheet(f"""
            QFrame#headerCard {{
                background-color: {theme.ACCENT_LIGHT};
                border: none;
                border-left: 4px solid {theme.ACCENT};
            }}
            QFrame#headerCard QLabel {{
                border: none;
                background-color: transparent;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        name_lbl = QLabel(f"<i>{sci_name}</i>")
        name_lbl.setStyleSheet(
            f"color: {theme.ACCENT_DARK}; font-size: 20px; font-weight: 700;"
        )
        layout.addWidget(name_lbl)

        # Summary row: badge + status_display + SQS
        row = QHBoxLayout()
        row.setSpacing(10)

        if summary.get("is_key"):
            tier = summary.get("key_species_tier", "")
            badge_colour = {
                "Rare": "#c62828", "Scarce": "#ef6c00", "Priority": "#7cb342"
            }.get(tier, theme.TEXT_SECONDARY)
            badge = QLabel(f"  {tier} Key Species  ")
            badge.setStyleSheet(
                f"background-color: {badge_colour}; color: white; "
                f"font-weight: 700; font-size: 12px; padding: 4px 12px; "
                f"border-radius: 4px;"
            )
            row.addWidget(badge)
        elif not summary.get("is_invertebrate"):
            # Make scope explicit so users don't assume a missing badge is a bug
            note = QLabel("Non-invertebrate (key-species scope: invertebrates only)")
            note.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-style: italic;"
            )
            row.addWidget(note)

        display = summary.get("status_display", "")
        if display:
            status_lbl = QLabel(display)
            status_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: 600; color: {theme.TEXT_PRIMARY};"
            )
            row.addWidget(status_lbl)

        sqs = summary.get("sqs", 0)
        if sqs:
            sqs_lbl = QLabel(f"SQS: {sqs}")
            sqs_lbl.setStyleSheet(
                f"color: {theme.GOLD}; font-weight: 700; font-size: 14px;"
            )
            row.addWidget(sqs_lbl)

        row.addStretch()
        layout.addLayout(row)
        return card

    def _make_profile_card(self, profile_text, source):
        """A distinct card showing the species' profile paragraph."""
        card = QFrame()
        card.setObjectName("profileCard")
        card.setStyleSheet(f"""
            QFrame#profileCard {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_SM};
            }}
            QFrame#profileCard QLabel {{
                border: none;
                background-color: transparent;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        head = QLabel("About this species")
        head.setStyleSheet(
            f"color: {theme.TEXT_HEADING}; font-size: 13px; font-weight: 600;"
        )
        layout.addWidget(head)

        body = QLabel(profile_text)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 13px; line-height: 1.4;"
        )
        layout.addWidget(body)

        if source:
            src = QLabel(f"Source: {source}")
            src.setWordWrap(True)
            src.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-style: italic;"
            )
            layout.addWidget(src)
        return card

    def _get_track_entries(self, summary, track_key):
        """Normalise a track value from get_species_conservation_summary
        into a list of entry dicts (or empty list)."""
        val = summary.get(track_key)
        if val is None:
            return []
        if isinstance(val, list):
            return val  # already a list of entry dicts
        if isinstance(val, dict):
            return [val]  # single entry dict
        return []

    def _make_track_card(self, label, sublabel, entries):
        """Card for a status track. Handles single or multiple entries."""
        card = QFrame()
        card.setObjectName("trackCard")
        card.setStyleSheet(f"""
            QFrame#trackCard {{
                background-color: transparent;
                border: none;
                border-bottom: 1px solid {theme.SEPARATOR};
            }}
            QFrame#trackCard QLabel {{
                border: none;
                background-color: transparent;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        # Left: track label + sublabel
        left = QVBoxLayout()
        left.setSpacing(2)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_HEADING}; font-size: 13px; font-weight: 600;"
        )
        left.addWidget(lbl)
        sub = QLabel(sublabel)
        sub.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        left.addWidget(sub)
        if len(entries) > 1:
            count = QLabel(f"{len(entries)} entries")
            count.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 10px; font-style: italic;"
            )
            left.addWidget(count)
        layout.addLayout(left)

        layout.addStretch()

        # Right: stack of value badges (one per entry)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        for entry in entries:
            entry_box = self._make_entry_widget(entry)
            right.addWidget(entry_box, 0, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(right)
        return card

    def _make_entry_widget(self, entry):
        """A single entry within a track card -- value badge + detail + source."""
        wrap = QFrame()
        wrap.setStyleSheet("background-color: transparent; border: none;")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        wl.setAlignment(Qt.AlignmentFlag.AlignRight)

        value = entry.get("value", "")
        detail = entry.get("detail")
        source = entry.get("source", "")
        iucn = entry.get("iucn_version", "")

        # Value badge -- if there's a detail (e.g. "Breeding"), show value
        # with a small detail line beneath
        if value:
            colour = theme.status_colour(value)
            text = value
            val_lbl = QLabel(f"  {text}  ")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl.setMinimumWidth(60)
            val_lbl.setStyleSheet(
                f"background-color: {colour}; color: white; "
                f"font-weight: 700; font-size: 14px; padding: 6px 16px; "
                f"border-radius: 4px;"
            )
            wl.addWidget(val_lbl, 0, Qt.AlignmentFlag.AlignRight)

        if detail:
            d = QLabel(detail)
            d.setAlignment(Qt.AlignmentFlag.AlignRight)
            d.setWordWrap(True)
            d.setMaximumWidth(350)
            d.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 500;"
            )
            wl.addWidget(d, 0, Qt.AlignmentFlag.AlignRight)

        if iucn and iucn != "2001":
            ver = QLabel(f"({iucn} guidelines)")
            ver.setAlignment(Qt.AlignmentFlag.AlignRight)
            ver.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 10px; font-style: italic;"
            )
            wl.addWidget(ver, 0, Qt.AlignmentFlag.AlignRight)

        if source:
            src = QLabel(source)
            src.setAlignment(Qt.AlignmentFlag.AlignRight)
            src.setWordWrap(True)
            src.setMaximumWidth(350)
            src.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 10px;")
            wl.addWidget(src, 0, Qt.AlignmentFlag.AlignRight)

        return wrap

    # ============================================================
    # Cleanup
    # ============================================================
    def _clear_results(self):
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_profile(self):
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.profile_layout.addStretch()
