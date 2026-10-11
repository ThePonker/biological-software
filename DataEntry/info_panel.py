"""Live species info panel (display only -- nothing here is ever stored).

Mirrors Tabella's rows 1-3: a species/taxon line, a conservation summary, and recording history.
Data comes from direct SQL: record counts from observatum.db (the connection the grid already
holds) and conservation from codex.db (opened read-only). Taxon fields come from the row itself
(captured when the species was picked), so no extra lookup is needed for those.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional, Dict, Tuple

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from DataEntry import theme
from DataEntry import species_dist_map as _src
from DataEntry.banner_layout import BannerCard, ElidedCheckBox, banner_height

# QSettings key per map source -- used by both the restore block and _on_source_toggle.
SRC_SETTING_KEYS = {
    "personal": "srcPersonal",
    "commercial": "srcCommercial",
    "collection": "srcCollection",
    "rs": "srcRS",
    "staging": "srcStaging",
}

_BANNER_H = 194  # least height of the banner cards; taller if the font needs it (R9-8)

# Conservation chips sit in one 316 px row: full labels were cut off ("Priority (NER",
# "Protected (B" -- L22, 10 Oct). The chip shows a short form; its tooltip the full label.
_PRIORITY_SHORT = {
    "NERC S.41 England": "S.41",
    "Scottish Biodiversity List": "SBL",
    "Env (Wales) Act S7": "S7",
    "NI Priority Species": "NI Priority",
    "UK BAP": "UK BAP",
}
_CHIP_MAX = 14   # characters; anything longer is shortened with an ellipsis


def chip_text(label: str) -> str:
    """The short text a conservation chip shows for `label` (its tooltip keeps `label`)."""
    label = (label or "").strip()
    if label.startswith("Priority (") and label.endswith(")"):
        inner = label[len("Priority ("):-1]
        return _PRIORITY_SHORT.get(inner, "Priority")
    if label.startswith("Protected"):
        return "Protected"
    if len(label) > _CHIP_MAX:
        return label[:_CHIP_MAX - 1].rstrip() + "\u2026"
    return label


class _FlowRow(QWidget):
    """A single horizontal strip of small widgets (chips/pills), left-aligned.

    Keeps a fixed height whether or not it has items, so the readout never changes size.
    What doesn't fit the width is folded into a "+n" chip whose tooltip names the rest, so
    nothing is ever cut off whatever the font (Windows' Segoe UI is wider: PC test, 10 Oct).
    """
    SPACING = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QLayout, QSizePolicy
        self.setFixedHeight(22)
        # the chips must never widen the readout: the row takes the width it is given and
        # folds what doesn't fit (a layout minimum would otherwise force the width up)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._lay = QHBoxLayout(self)
        self._lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._lay.setContentsMargins(0, 2, 0, 0)
        self._lay.setSpacing(self.SPACING)
        self._lay.addStretch(1)
        self._items = []
        self._more = None

    def set_items(self, widgets):
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
                w.setParent(None)        # leave now, not at the next event loop turn
                w.deleteLater()
        self._items = list(widgets)
        for w in self._items:
            self._lay.addWidget(w)
        self._more = QLabel("")
        self._more.setStyleSheet(theme.badge_qss("default") + " border: none;")
        self._more.hide()
        self._lay.addWidget(self._more)
        self._lay.addStretch(1)
        self._fit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def visible_count(self) -> int:
        return sum(1 for w in self._items if not w.isHidden())

    def _fit(self):
        """Show the items that fit; fold the rest into "+n" (tooltip lists them)."""
        if not self._items or self._more is None:
            return
        avail = self.contentsRect().width()
        if avail <= 0:                              # not laid out yet: show all for now
            for w in self._items:
                w.show()
            self._more.hide()
            return
        widths = [w.sizeHint().width() for w in self._items]
        total = sum(widths) + self.SPACING * (len(widths) - 1)
        if total <= avail:
            for w in self._items:
                w.show()
            self._more.hide()
            return
        n = len(self._items)
        keep = 0
        for k in range(n - 1, -1, -1):              # most items that fit beside a "+n" chip
            self._more.setText(f"+{n - k}")
            more_w = self._more.sizeHint().width()
            used = sum(widths[:k]) + self.SPACING * k + more_w
            if used <= avail:
                keep = k
                break
        self._more.setText(f"+{n - keep}")
        hidden = self._items[keep:]
        self._more.setToolTip("\n".join((w.toolTip() or w.text()) for w in hidden))
        for i, w in enumerate(self._items):
            w.setVisible(i < keep)
        self._more.show()


class _PopOut(QWidget):
    """A resizable top-level window hosting one live map widget."""
    def __init__(self, title, map_widget, on_close):
        super().__init__(None)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self._on_close = on_close
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(map_widget)

    def closeEvent(self, e):
        try:
            self._on_close()
        except Exception:
            pass
        super().closeEvent(e)


class InfoService:
    """Read-only lookups for the info panel. Fails soft: missing tables -> blanks/zeros."""

    def __init__(self, main_conn: sqlite3.Connection, codex_path: Optional[str] = None):
        self._main = main_conn
        self._codex_path = codex_path if (codex_path and os.path.exists(codex_path)) else None
        self._codex: Optional[sqlite3.Connection] = None

    def _codex_conn(self) -> Optional[sqlite3.Connection]:
        if self._codex_path is None:
            return None
        if self._codex is None:
            try:
                self._codex = sqlite3.connect(f"file:{self._codex_path}?mode=ro", uri=True)
            except sqlite3.Error:
                self._codex = None
        return self._codex

    def counts(self, tvk: str) -> Tuple[int, int, int]:
        """(personal, commercial, specimens) for a TVK from observatum.db."""
        if not tvk:
            return (0, 0, 0)
        personal = commercial = specimens = 0
        try:
            cur = self._main.execute(
                "SELECT record_type, COUNT(*) FROM observations WHERE species_tvk=? GROUP BY record_type",
                (tvk,),
            )
            for rt, n in cur.fetchall():
                if (str(rt or "")).lower().startswith("comm"):
                    commercial += n
                else:
                    personal += n
        except sqlite3.Error:
            pass
        try:
            row = self._main.execute(
                "SELECT COUNT(*) FROM specimens WHERE species_tvk=?", (tvk,)
            ).fetchone()
            specimens = row[0] if row else 0
        except sqlite3.Error:
            pass
        return (personal, commercial, specimens)

    def specimen_sexes(self, tvk: str):
        """(male, female, other) specimens held for a TVK.

        `other` is everything not resolvable to male or female -- unsexed,
        blank, and "Unknown" alike. Kept separate from counts() so the existing
        three-tuple contract is untouched.
        """
        if not tvk:
            return (0, 0, 0)
        try:
            rows = self._main.execute(
                "SELECT sex FROM specimens WHERE species_tvk=?", (tvk,)
            ).fetchall()
        except sqlite3.Error:
            return (0, 0, 0)
        try:
            from shared.sex_summary import count_sexes
        except ImportError:
            return (0, 0, len(rows))
        return count_sexes(r[0] for r in rows)

    def conservation(self, tvk: str, vc_number=None) -> str:
        """Compact conservation summary (the chips' labels), or '' if none/unavailable."""
        if not tvk or self._codex_conn() is None:
            return ""
        labels = [label for label, _ in self.conservation_chips(tvk, vc_number)]
        return "   ".join(labels) if labels else "No conservation status"

    @staticmethod
    def jurisdiction_for_vc(vc_number) -> str:
        """The country whose priority list and legal instruments apply at this VC.

        Examen's rule (examen_data.country_for_vc, review EXA2). No readable VC -> England,
        Examen's default. Before 10 Oct the chips took whichever priority row came first,
        so an Oxfordshire record could show 'NI Priority Species' (review DE6).
        """
        try:
            from Examen.examen_data import country_for_vc, DEFAULT_JURISDICTION
        except Exception:
            return "England"
        try:
            return country_for_vc(int(vc_number)) or DEFAULT_JURISDICTION
        except (TypeError, ValueError):
            return DEFAULT_JURISDICTION

    def conservation_chips(self, tvk: str, vc_number=None):
        """List of (label, kind) for coloured chips. kind in threat/rarity/priority/legal/other.

        Priority listings and NI-only legal instruments are shown only where they apply:
        the record's country from its vice-county (jurisdiction_for_vc), filtered by the
        same rules as Codex/Examen's Key-species decision. Threat and rarity are GB-wide.
        """
        if not tvk:
            return []
        conn = self._codex_conn()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                "SELECT status_track, status_value, status_detail FROM status_summary WHERE tvk=? "
                "ORDER BY rowid",
                (tvk,),
            ).fetchall()
        except sqlite3.Error:
            return []
        from types import SimpleNamespace
        from shared.repositories.codex_repository import _legal_applies, _priority_applies
        where = self.jurisdiction_for_vc(vc_number)
        by: Dict[str, Tuple[str, str]] = {}
        priority, legal = [], []
        for track, value, detail in rows:
            if track == "priority":
                if _priority_applies(value, where):
                    priority.append((value, detail))
            elif track == "legal_protection":
                if _legal_applies(SimpleNamespace(value=value, detail=detail), where):
                    legal.append((value, detail))
            else:
                by.setdefault(track, (value, detail))
        chips = []
        if "threat_iucn_2001" in by:
            chips.append((by["threat_iucn_2001"][0], "threat"))
        elif "threat_iucn_legacy" in by:
            chips.append((by["threat_iucn_legacy"][0], "threat"))
        if "rarity_modern" in by:
            chips.append((by["rarity_modern"][0], "rarity"))
        elif "rarity_legacy" in by:
            chips.append((by["rarity_legacy"][0], "rarity"))
        if "bocc" in by:
            chips.append(("BoCC " + (by["bocc"][0] or ""), "threat"))
        if priority:
            # the country's own list before UK BAP
            priority.sort(key=lambda vd: "bap" in (vd[0] or "").lower())
            det = priority[0][1] or priority[0][0]
            chips.append(("Priority" + (f" ({det})" if det else ""), "priority"))
        if legal:
            det = legal[0][1]
            chips.append(("Protected" + (f" ({det})" if det else ""), "legal"))
        return [(l, k) for (l, k) in chips if l and l.strip()]


class InfoPanel(QWidget):
    """Three compact lines: species/taxon, conservation, recording history."""

    def __init__(self, service: InfoService, vc_service=None, geojson_path=None,
                 tiles_dir=None, dist_service=None, maps_dir=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._svc = service
        self._vc = vc_service
        self.setStyleSheet("background: transparent; border: none;")
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        self._outer = outer
        self._controls_widget = None
        self._banner_cards = []   # every card in the row: all share one height (_fit_banner)
        self._collapsible = []
        from PySide6.QtWidgets import QSizePolicy
        # the width is the window's; _fit_width sets the real minimum (the cards that must stay)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        # remember construction params so pop-out windows can build their own live map copies
        self._tiles_dir = tiles_dir
        self._maps_dir = maps_dir
        self._geojson_path = geojson_path
        self._dist_service = dist_service
        self._current_row = None
        self._pending_fn = None
        self._job_mode = "Personal"
        self._wb_fn = None
        self._popout_loc = None
        self._popout_loc_win = None
        self._popout_dist = None
        self._popout_dist_win = None
        self._settings = QSettings()

        text_col = QVBoxLayout()
        text_col.setContentsMargins(12, 10, 12, 10)
        text_col.setSpacing(2)
        self._l1 = QLabel()
        self._l1.setStyleSheet(f"color: {theme.INK}; font-size: 16px; font-weight: 700; border: none; background: transparent;")
        self._l2 = QLabel()
        self._l2.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px; border: none; background: transparent;")
        self._l3 = QLabel()
        self._l3.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px; border: none; background: transparent;")
        self._l4 = QLabel()  # location warning (grid-ref guardrail)
        self._l4.setStyleSheet(f"color: {theme.CLAY}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        self._l1.setFixedHeight(42)   # room for a two-line name; 1-line names just sit at the top
        self._l2.setFixedHeight(18)
        self._l3.setFixedHeight(18)
        self._l4.setFixedHeight(16)
        for lab in (self._l1, self._l2, self._l3, self._l4):
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            text_col.addWidget(lab)
        # conservation chips + count pills (flow rows)
        self._chips_row = _FlowRow()
        self._pills_row = _FlowRow()
        text_col.addWidget(self._chips_row)
        text_col.addWidget(self._pills_row)
        text_col.addStretch(1)
        # fixed height so selecting/deselecting a row changes only the text, never the layout.
        # 316 wide when there's room (272 was too narrow once the specimen pill gained its sex
        # breakdown); it narrows on a small window -- the chip rows fold into "+n" (R9-8)
        readout_w = BannerCard(316, 240)
        readout_w.setLayout(text_col)
        readout_w.setStyleSheet(theme.card_qss())
        self._banner_cards.append(readout_w)
        outer.addWidget(readout_w, 0, Qt.AlignmentFlag.AlignTop)
        wb_card = self._build_workbook_card()
        traps_card = self._build_locations_card()
        outer.addWidget(wb_card, 0, Qt.AlignmentFlag.AlignTop)
        outer.addWidget(traps_card, 0, Qt.AlignmentFlag.AlignTop)
        # on a window too narrow for every card even at its smallest, these step aside, in
        # this order, and come back when there's room (R9-8: the legend was cut off instead)
        self._collapsible = [traps_card, wb_card]

        # ---- maps area ----
        maps_card = BannerCard(330, 0)   # no narrower than its two maps (layout minimum)
        maps_card.setStyleSheet(theme.card_qss())
        maps_col = QVBoxLayout(maps_card)
        maps_col.setContentsMargins(10, 8, 10, 8)
        maps_col.setSpacing(3)

        def _pop_btn(tip):
            b = QPushButton("\u2922")  # pop-out glyph
            b.setToolTip(tip); b.setFixedSize(20, 18); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"border:1px solid {theme.LINE}; border-radius:3px; background:{theme.CARD};"
                            f"color:{theme.SLATE}; font-size:11px;")
            return b

        # row 1: map visibility toggles + pop-out buttons
        vis = QHBoxLayout(); vis.setSpacing(8)
        # labels shorten with "..." rather than widen the card past its maps (R3 fix)
        self._chk_loc = ElidedCheckBox("This record")
        self._btn_pop_loc = _pop_btn("Pop out the location map")
        self._chk_dist = ElidedCheckBox("All my records")
        self._btn_pop_dist = _pop_btn("Pop out the distribution map")
        for chk in (self._chk_loc, self._chk_dist):
            chk.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; border: none;")
        vis.addWidget(self._chk_loc); vis.addWidget(self._btn_pop_loc)
        vis.addSpacing(8)
        vis.addWidget(self._chk_dist); vis.addWidget(self._btn_pop_dist)
        vis.addStretch(1)
        maps_col.addLayout(vis)

        # (source toggles now live in the legend panel to the right of the maps)

        maps_row = QHBoxLayout(); maps_row.setSpacing(8); maps_row.addStretch(1)

        # location map: prefer OS raster, else vector VC outline, else none
        self._map = None
        try:
            from DataEntry.raster_map import RasterMiniMap
            rm = RasterMiniMap(tiles_dir, vc_service)
            if rm.has_data():
                self._map = rm
            else:
                rm.deleteLater()
        except Exception:
            self._map = None
        if self._map is None:
            try:
                from DataEntry.vc_map import MiniMap
                mm = MiniMap(geojson_path, vc_service)
                if mm.has_data():
                    self._map = mm
                else:
                    mm.deleteLater()
            except Exception:
                self._map = None
        if self._map is not None:
            maps_row.addWidget(self._map, 0, Qt.AlignmentFlag.AlignTop)
            self._chk_loc.toggled.connect(self._map.setVisible)
            self._btn_pop_loc.clicked.connect(self._popout_location)
        else:
            self._chk_loc.setEnabled(False); self._btn_pop_loc.setEnabled(False)

        # distribution map
        self._dist = None
        try:
            from DataEntry.species_dist_map import DistributionMiniMap
            dm = DistributionMiniMap(geojson_path, dist_service, tiles_dir=tiles_dir, maps_dir=maps_dir)
            if dm.has_data():
                self._dist = dm
                maps_row.addWidget(dm, 0, Qt.AlignmentFlag.AlignTop)
                self._chk_dist.toggled.connect(dm.setVisible)
                self._btn_pop_dist.clicked.connect(self._popout_distribution)
            else:
                dm.deleteLater()
        except Exception:
            self._dist = None
        if self._dist is None:
            self._chk_dist.setEnabled(False); self._btn_pop_dist.setEnabled(False)
            # (_chk_rs/_chk_spec no longer exist -- the source checkboxes are the legend's
            # _src_chk, built only with a map; this line crashed the panel when no map loaded)

        maps_row.addStretch(1)
        maps_col.addLayout(maps_row)
        maps_col.addStretch(1)
        # controls get inserted at index 1 later; a flexible spacer here keeps readout+controls on
        # the left and pins BOTH maps (fixed size, side by side) to the right so they never clip.
        outer.addStretch(1)
        if self._map is not None or self._dist is not None:
            self._banner_cards.append(maps_card)
            outer.addWidget(maps_card, 0, Qt.AlignmentFlag.AlignTop)
            outer.addWidget(self._build_legend(), 0, Qt.AlignmentFlag.AlignTop)
        self._fit_banner()

        # restore persisted toggle states (default all on), then wire persistence + recompute
        S = self._settings
        self._chk_loc.setChecked(S.value("DataEntry/mapShowLocation", True, type=bool))
        self._chk_dist.setChecked(S.value("DataEntry/mapShowDistribution", True, type=bool))
        self._chk_loc.toggled.connect(lambda v: S.setValue("DataEntry/mapShowLocation", bool(v)))
        self._chk_dist.toggled.connect(lambda v: S.setValue("DataEntry/mapShowDistribution", bool(v)))
        _keys = SRC_SETTING_KEYS
        if getattr(self, "_src_chk", None):   # legend only exists when a map was built
            for k in _src.SOURCE_ORDER:
                self._src_chk[k].setChecked(S.value("DataEntry/" + _keys[k], True, type=bool))
                self._src_chk[k].toggled.connect(self._on_source_toggle)

        self.clear()

    def _build_legend(self):
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
        cols = _src.source_colours()
        panel = BannerCard(168, 168)    # labels shorten with "..." if the font is wide (R9-8)
        panel.setStyleSheet(theme.card_qss())
        self._banner_cards.append(panel)
        v = QVBoxLayout(panel); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(4)
        title = QLabel("Records"); title.setStyleSheet(
            f"color: {theme.HEADING}; font-size: 12px; font-weight: 700; border: none; background: transparent;")
        v.addWidget(title)
        self._src_chk = {}; self._src_swatch = {}; self._src_lbl = {}
        for k in _src.SOURCE_ORDER:
            row = QHBoxLayout(); row.setSpacing(6)
            sw = QLabel(); sw.setFixedSize(11, 11)
            sw.setStyleSheet(f"background: {cols[k]}; border-radius: 5px; border: none;")
            chk = ElidedCheckBox(_src.SOURCE_LABELS[k]); chk.setChecked(True)
            chk.setStyleSheet(f"color: {theme.INK}; font-size: 11px; border: none; background: transparent;")
            row.addWidget(sw); row.addWidget(chk, 1)
            v.addLayout(row)
            self._src_chk[k] = chk; self._src_swatch[k] = sw; self._src_lbl[k] = chk
        self._dist_count = QLabel("")
        self._dist_count.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; border: none; background: transparent;")
        self._dist_count.setWordWrap(True)
        v.addSpacing(4); v.addWidget(self._dist_count)
        v.addStretch(1)
        return panel

    def _style_legend_row(self, k):
        on = self._src_chk[k].isChecked()
        cols = _src.source_colours()
        c = cols[k] if on else theme.DISABLED_BG
        self._src_swatch[k].setStyleSheet(f"background: {c}; border-radius: 5px; border: none;")
        txt = theme.INK if on else theme.DISABLED_TEXT
        self._src_chk[k].setStyleSheet(
            f"color: {txt}; font-size: 11px; border: none; background: transparent;")

    def _enabled_sources(self):
        if not getattr(self, "_src_chk", None):
            return {k: True for k in _src.SOURCE_ORDER}
        return {k: self._src_chk[k].isChecked() for k in _src.SOURCE_ORDER}

    def _on_source_toggle(self, _=None):
        keys = SRC_SETTING_KEYS
        for k in _src.SOURCE_ORDER:
            self._settings.setValue("DataEntry/" + keys[k], self._src_chk[k].isChecked())
            self._style_legend_row(k)
        self._refresh_distribution()

    def _refresh_distribution(self):
        tvk = ((self._current_row or {}).get("species_tvk") or "").strip()
        name = ((self._current_row or {}).get("species_name") or "").strip()
        enabled = self._enabled_sources()
        if self._dist is not None:
            self._dist.update_for_species(tvk if name else None, enabled)
        if self._popout_dist is not None:
            self._popout_dist.update_for_species(tvk if name else None, enabled)
        if getattr(self, '_dist_count', None) is not None:
            n = self._dist._count if self._dist is not None else 0
            self._dist_count.setText(f"{n:,} \u00d7 1 km squares" if name else "")

    def _popout_location(self):
        if self._popout_loc_win is not None:
            self._popout_loc_win.raise_(); self._popout_loc_win.activateWindow(); return
        from DataEntry.raster_map import RasterMiniMap
        from DataEntry.vc_map import MiniMap
        try:
            m = RasterMiniMap(self._tiles_dir, self._vc, window_m=16000, resizable=True)
            if not m.has_data():
                m.deleteLater(); m = MiniMap(self._geojson_path, self._vc)
        except Exception:
            m = MiniMap(self._geojson_path, self._vc)
        self._popout_loc = m
        def _closed_loc():
            self._popout_loc = None; self._popout_loc_win = None
        w = _PopOut("Location \u2014 this record", m, _closed_loc)
        self._popout_loc_win = w
        if self._current_row is not None:
            m.update_for_row(self._current_row)
        w.resize(460, 460); w.show()

    def _popout_distribution(self):
        if self._popout_dist_win is not None:
            self._popout_dist_win.raise_(); self._popout_dist_win.activateWindow(); return
        from DataEntry.species_dist_map import DistributionMiniMap
        m = DistributionMiniMap(self._geojson_path, self._dist_service, resizable=True,
                                tiles_dir=self._tiles_dir, maps_dir=self._maps_dir)
        self._popout_dist = m
        def _closed_dist():
            self._popout_dist = None; self._popout_dist_win = None
        w = _PopOut("Distribution \u2014 all my records", m, _closed_dist)
        self._popout_dist_win = w
        self._refresh_distribution()
        w.resize(460, 500); w.show()

    def clear(self):
        self._current_row = None
        self._l1.setText("Select a species row to see details")
        self._l2.setText("")
        self._l3.setText("")
        self._l4.setText("")
        if hasattr(self, "_chips_row"):
            self._chips_row.set_items([])
        if hasattr(self, "_pills_row"):
            self._pills_row.set_items([])
        if self._map is not None:
            self._map.update_for_row(None)
        if self._popout_loc is not None:
            self._popout_loc.update_for_row(None)
        if self._dist is not None:
            self._dist.clear()
        if self._popout_dist is not None:
            self._popout_dist.update_for_species(None, self._enabled_sources())

    def set_controls_widget(self, w):
        """Insert the entry controls (boxes + buttons) as the middle column of the banner."""
        self._controls_widget = w
        # place between the readout (index 0) and the maps column
        self._outer.insertWidget(1, w, 0, Qt.AlignmentFlag.AlignTop)
        self._banner_cards.append(w)
        self._fit_banner()

    def _fit_banner(self):
        """Give every banner card one height: _BANNER_H, or more if a card's rows need it at
        this font (R9-8: a fixed 194 px squeezed the controls' buttons and clipped their text
        on Windows)."""
        cards = getattr(self, "_banner_cards", None)   # changeEvent can come mid-build
        if not cards:
            return
        h = banner_height(_BANNER_H, cards)
        for c in cards:
            c.setFixedHeight(h)
        self._fit_width()

    @staticmethod
    def _least_width(c) -> int:
        """The narrowest a card can be, measured from its contents at this font (R3 fix: a
        fixed minimum under-counted on Wil's PC, so cards were squeezed and the row overran)."""
        if isinstance(c, BannerCard):
            return c.least_width()
        c.ensurePolished()
        return max(c.minimumWidth(), c.minimumSizeHint().width())

    def _row_width(self, cards) -> int:
        """Width the banner row needs to show `cards` at their narrowest."""
        if not cards:
            return 0
        m = self._outer.contentsMargins()
        return (sum(self._least_width(c) for c in cards)
                + self._outer.spacing() * (len(cards) - 1) + m.left() + m.right())

    def _fit_width(self):
        """Hide the collapsible cards (Traps, then This workbook) only while the row can't fit
        them at their smallest; nothing is ever drawn past the right edge."""
        self._fit_pending = False
        cards = getattr(self, "_banner_cards", None)
        if not cards:
            return
        for c in cards:
            if isinstance(c, BannerCard):
                c.refit()
            if not getattr(c, "_de_watched", False):   # re-fit when a card's contents change
                c.installEventFilter(self)
                c._de_watched = True
        steps = [c for c in self._collapsible if c in cards]
        keep = [c for c in cards if c not in steps]
        # what must stay sets the least width; if even that is more than the window, the
        # banner's scroll area (BannerScroll) shows a scroll bar: the window isn't widened
        least = self._row_width(keep)
        if self.minimumWidth() != least:
            self.setMinimumWidth(least)
        avail = self.width()
        hide = []
        for k in range(len(steps) + 1):
            hide = steps[:k]
            # a card steps aside only when the row can't hold it even at its narrowest:
            # a narrower card (the readout folds its chips into "+n") beats a missing one
            if self._row_width([c for c in cards if c not in hide]) <= avail:
                break
        for c in steps:
            if c.isHidden() != (c in hide):
                c.setVisible(c not in hide)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit_width()

    def eventFilter(self, obj, e):
        # a card's contents changed size (e.g. "Back to entry order" appeared): measure again
        # once the event loop is free, so many changes cost one re-fit
        from PySide6.QtCore import QEvent, QTimer
        if (e.type() == QEvent.Type.LayoutRequest and obj in getattr(self, "_banner_cards", ())
                and not getattr(self, "_fit_pending", False)):
            self._fit_pending = True
            QTimer.singleShot(0, self, self._fit_width)
        return super().eventFilter(obj, e)

    def banner_height(self) -> int:
        return self._banner_cards[0].height() if self._banner_cards else 0

    def changeEvent(self, e):
        super().changeEvent(e)
        from PySide6.QtCore import QEvent
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit_banner()

    def showEvent(self, e):
        self._fit_banner()          # fonts and style sheets are final by now
        super().showEvent(e)

    @staticmethod
    def _chip(label, kind):
        k = "success" if label.strip().upper() in ("LC", "LEAST CONCERN") else kind
        w = QLabel(chip_text(label))       # short form; the whole label on hover (L22)
        w.setToolTip(label)
        w.setStyleSheet(theme.badge_qss(k) + " border: none;")
        return w

    @staticmethod
    def _pill(label):
        w = QLabel(label)
        w.setStyleSheet(theme.badge_qss("default") + " border: none;")
        return w

    def _location_warning(self, row: Dict) -> str:
        gr = (row.get("grid_ref") or "").strip()
        if not gr or not self._vc:
            return ""
        try:
            ok, msg = self._vc.validate_grid_ref(gr)
        except Exception:
            return ""
        if not ok:
            return f"\u26a0 Grid ref: {msg}"
        # on a vice-county boundary (F29, I3b): say which VCs and how much of each
        try:
            a = self._vc.assess(gr) if hasattr(self._vc, "assess") else None
        except Exception:
            a = None
        if a and a.get("boundary"):
            return f"\u26a0 {a['note']} \u2014 check the VC"
        if a is None and "warning" in (msg or "").lower():
            return f"\u26a0 {msg}"
        return ""

    _WB_PER_COL = 6   # orders per column (2 columns -> up to 12 shown, then "+N more")

    def _build_locations_card(self):
        """Distinct trap / sub-location / grid-ref combinations in this job. Click to copy."""
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QScrollArea
        card = BannerCard(210, 150)
        card.setStyleSheet(theme.card_qss())
        self._banner_cards.append(card)
        v = QVBoxLayout(card); v.setContentsMargins(12, 10, 12, 6); v.setSpacing(4)

        head = QLabel("Traps")
        head.setStyleSheet(
            f"color: {theme.HEADING}; font-size: 13px; font-weight: 700;"
            " border: none; background: transparent;")
        v.addWidget(head)

        self._loc_hint = QLabel("Click to copy")
        self._loc_hint.setStyleSheet(
            f"color: {theme.FAINT}; font-size: 11px; border: none; background: transparent;")
        v.addWidget(self._loc_hint)

        self._loc_scroll = QScrollArea()
        self._loc_scroll.setWidgetResizable(True)
        self._loc_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._loc_scroll.setStyleSheet("background: transparent; border: none;")
        self._loc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._loc_body = QWidget()
        self._loc_body.setStyleSheet("background: transparent;")
        self._loc_lay = QVBoxLayout(self._loc_body)
        self._loc_lay.setContentsMargins(0, 0, 0, 0)
        self._loc_lay.setSpacing(1)
        self._loc_lay.addStretch(1)
        self._loc_scroll.setWidget(self._loc_body)
        v.addWidget(self._loc_scroll, 1)
        return card

    def set_locations_provider(self, fn):
        """fn() -> [(sub_location, trap_number, grid_ref, count), ...] most-used first."""
        self._loc_fn = fn
        self.refresh_locations()

    def _copy_grid_ref(self, ref: str):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        QApplication.clipboard().setText(ref)
        self._loc_hint.setText(f"Copied {ref}")
        QTimer.singleShot(1800, lambda: self._loc_hint.setText("Click to copy"))

    def refresh_locations(self):
        from PySide6.QtWidgets import QLabel
        fn = getattr(self, "_loc_fn", None)
        if fn is None or not hasattr(self, "_loc_lay"):
            return
        while self._loc_lay.count():
            it = self._loc_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        try:
            entries = fn() or []
        except Exception:
            entries = []

        if not entries:
            none_lab = QLabel("No traps recorded yet")
            none_lab.setStyleSheet(
                f"color: {theme.FAINT}; font-size: 12px; border: none; background: transparent;")
            self._loc_lay.addWidget(none_lab)
            self._loc_lay.addStretch(1)
            return

        last_sub = object()
        for sub, trap, ref, n in entries:
            if sub != last_sub:
                last_sub = sub
                hdr = QLabel(sub or "No sub-location")
                hdr.setStyleSheet(
                    f"color: {theme.HEADING}; font-size: 11px; font-weight: 700;"
                    " padding: 4px 0 1px 0; border: none; background: transparent;")
                self._loc_lay.addWidget(hdr)
            text = (str(trap) + "  \u2014  " + ref) if trap else ref
            lab = QLabel(text)
            lab.setToolTip(f"{ref}\n{n} record(s) \u2014 click to copy")
            lab.setCursor(Qt.CursorShape.PointingHandCursor)
            lab.setWordWrap(True)
            lab.setStyleSheet(
                f"color: {theme.INK}; font-size: 11px; padding: 1px 3px 1px 12px;"
                " border: none; background: transparent;")
            lab.mousePressEvent = (lambda _e, r=ref: self._copy_grid_ref(r))
            self._loc_lay.addWidget(lab)
        self._loc_lay.addStretch(1)

    def _build_workbook_card(self):
        from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QLabel
        card = BannerCard(330, 230)
        card.setStyleSheet(theme.card_qss())
        self._banner_cards.append(card)
        v = QVBoxLayout(card); v.setContentsMargins(12, 10, 12, 10); v.setSpacing(4)
        head = QLabel("This workbook")
        head.setStyleSheet(f"color: {theme.HEADING}; font-size: 13px; font-weight: 700; border: none; background: transparent;")
        v.addWidget(head)
        self._wb_title = QLabel("No records yet")
        self._wb_title.setStyleSheet(f"color: {theme.INK}; font-size: 13px; font-weight: 600; border: none; background: transparent;")
        self._wb_title.setWordWrap(True)
        v.addWidget(self._wb_title)
        cap = QLabel("By order")
        cap.setStyleSheet(f"color: {theme.FAINT}; font-size: 11px; font-weight: 600; border: none; background: transparent;")
        v.addSpacing(2); v.addWidget(cap)
        self._wb_grid = QGridLayout()
        self._wb_grid.setContentsMargins(0, 0, 0, 0)
        self._wb_grid.setHorizontalSpacing(14); self._wb_grid.setVerticalSpacing(2)
        self._wb_grid.setColumnStretch(0, 1); self._wb_grid.setColumnStretch(1, 1)
        v.addLayout(self._wb_grid)
        v.addStretch(1)
        return card

    def _clear_wb_grid(self):
        while self._wb_grid.count():
            it = self._wb_grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def set_workbook_provider(self, fn):
        """fn() -> (records, species, [(order, count), ...]) for the current job (staged only)."""
        self._wb_fn = fn
        self.refresh_workbook()

    def refresh_workbook(self):
        if not getattr(self, "_wb_fn", None) or not hasattr(self, "_wb_title"):
            return
        try:
            got = self._wb_fn()
            records, species, breakdown = got[0], got[1], got[2]
            individuals = got[3] if len(got) > 3 else None
        except Exception:
            return
        if not records:
            self._wb_title.setText("No records yet")
            self._clear_wb_grid()
            return
        _t = f"{records} record{'s' if records != 1 else ''}  \u00b7  {species} species"
        if individuals is not None:
            _t += f"  \u00b7  {individuals} individuals"
        self._wb_title.setText(_t)
        from PySide6.QtWidgets import QLabel
        self._clear_wb_grid()
        cap = self._WB_PER_COL * 2
        top = breakdown[:cap]
        extra = len(breakdown) - len(top)
        cells = []
        for item in top:
            if len(item) >= 3:
                cells.append(f"{item[0]}  {item[1]} ({item[2]})")
            else:
                cells.append(f"{item[0]}  {item[1]}")
        if extra > 0:
            cells.append(f"+{extra} more")
        for i, txt in enumerate(cells):
            col = i // self._WB_PER_COL   # fill down column 0, then column 1
            rowp = i % self._WB_PER_COL
            lab = QLabel(txt)
            muted = txt.startswith("+")
            lab.setStyleSheet(
                f"color: {theme.FAINT if muted else theme.MUTED}; font-size: 12px;"
                f" border: none; background: transparent;")
            self._wb_grid.addWidget(lab, rowp, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def set_pending_provider(self, job_mode, fn):
        """job_mode = 'Personal'/'Commercial'; fn(tvk) -> count of staged rows for that species."""
        self._job_mode = job_mode or "Personal"
        self._pending_fn = fn
        self.refresh_counts()

    def _pending_for(self, tvk):
        """{"personal": n, "commercial": n} staged across all jobs."""
        blank = {"personal": 0, "commercial": 0}
        if not (self._pending_fn and tvk):
            return blank
        try:
            got = self._pending_fn(tvk)
        except Exception:
            return blank
        if isinstance(got, dict):
            return {"personal": int(got.get("personal", 0)),
                    "commercial": int(got.get("commercial", 0))}
        try:  # older provider returned a single number for the current mode
            n = int(got)
        except (TypeError, ValueError):
            return blank
        key = "commercial" if str(self._job_mode or "").lower().startswith("comm") else "personal"
        out = dict(blank); out[key] = n
        return out

    def _set_count_pills(self, tvk):
        p, c, s = self._svc.counts(tvk)
        pend = self._pending_for(tvk)
        pp, pc = pend["personal"], pend["commercial"]
        pt = f"Pers. {p}" + (f" (+{pp})" if pp else "")
        ct = f"Comm. {c}" + (f" (+{pc})" if pc else "")
        tip = ("Committed records in Observatum. Any bracketed figure is rows still "
               "in Data Entry staging, across every open workbook.")

        # Specimens held, with the sex breakdown where any has been recorded.
        # The bracket is omitted entirely when nothing is sexed -- saying
        # "7 unsexed" adds nothing the total does not already give.
        male = female = other = 0
        st = f"Spec. {s}"
        try:
            from shared.sex_summary import format_sex_summary
            male, female, other = self._svc.specimen_sexes(tvk)
            summary = format_sex_summary(male, female, other)
            if summary:
                st = f"Spec. {s} ({summary})"
        except (ImportError, AttributeError):
            pass

        spec_pill = self._pill(st)
        if male or female:
            spec_pill.setToolTip(
                f"{s} specimen(s) held \u2014 {male} male, {female} female"
                + (f", {other} not yet sexed" if other else "")
                + ".\nFrom the Insect Collection.")
        else:
            spec_pill.setToolTip(
                f"{s} specimen(s) held in the Insect Collection."
                + (" None sexed yet." if s else ""))

        pills = [self._pill(pt), self._pill(ct)]
        for w in pills:
            w.setToolTip(tip)
        pills.append(spec_pill)
        self._pills_row.set_items(pills)

    def refresh_counts(self):
        """Recompute just the count pills for the current species (live pending update)."""
        row = self._current_row or {}
        tvk = (row.get("species_tvk") or "").strip()
        name = (row.get("species_name") or "").strip()
        if name and tvk and hasattr(self, "_pills_row"):
            self._set_count_pills(tvk)

    def update_for_row(self, row: Optional[Dict]):
        self._current_row = row
        if self._map is not None:
            self._map.update_for_row(row)
        if self._popout_loc is not None:
            self._popout_loc.update_for_row(row)
        if not row:
            self.clear()
            return
        self._l4.setText(self._location_warning(row))  # grid-ref guardrail (independent of species)
        name = (row.get("species_name") or "").strip()
        self._refresh_distribution()  # updates inline + pop-out distribution with current source flags
        if not name:
            self._l1.setText("Select a species row to see details")
            self._l2.setText("")
            self._l3.setText("")
            return
        # Line 1: Species -- Common  [Family, Order]
        line1 = name
        common = (row.get("common_name") or "").strip()
        if common:
            line1 += f"  \u2014  {common}"
        self._l1.setText(line1)
        bits = [b for b in (row.get("family"), row.get("order_name")) if b]
        self._taxon_line = "  \u00b7  ".join(bits) if bits else ""

        tvk = (row.get("species_tvk") or "").strip()
        # Line 2: conservation as coloured chips (text line kept blank; chips carry it)
        self._l2.setText("")
        chips = []
        if tvk:
            for label, kind in self._svc.conservation_chips(tvk, row.get("vc_number")):
                chips.append(self._chip(label, kind))
            if not chips:
                self._l2.setText("No conservation status")
        self._chips_row.set_items(chips)
        # Line 3 -> family / order, then count pills
        if tvk:
            self._l3.setText(getattr(self, "_taxon_line", ""))
            self._set_count_pills(tvk)
        else:
            self._l3.setText("Unresolved species \u2014 no TVK, so no records/status shown")
            self._pills_row.set_items([])
