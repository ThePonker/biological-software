"""
Curator - Label Preview Widget
Black and white friendly, cascading sizes, cut lines between labels.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea
from PySide6.QtCore import Qt

RANK_OFFSET = {"Order":6,"Suborder":6,"Superfamily":4,"Family":2,"Subfamily":2,"Genus":0,"Species":0}

class LabelPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._cl = QVBoxLayout(self._container)
        self._cl.setContentsMargins(16, 16, 16, 16)
        self._cl.setSpacing(0)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def set_labels(self, labels, full_width=True, show_common=True,
                   show_my_specimens=False, show_my_species=False,
                   show_fauna=False, font_family="Helvetica", font_size=11):
        # Rebuild container fresh each time to avoid scroll issues
        old = self._scroll.takeWidget()
        if old:
            old.deleteLater()
        self._container = QWidget()
        self._cl = QVBoxLayout(self._container)
        self._cl.setContentsMargins(16, 16, 16, 16)
        self._cl.setSpacing(0)

        PAGE_HEIGHT_MM = 265
        cumulative_mm = 12.0
        page_num = 1

        for i, entry in enumerate(labels):
            if len(entry) == 6:
                name, rank, cn, specimens, my_species, gb_species = entry
            elif len(entry) == 5:
                name, rank, cn, specimens, gb_species = entry
                my_species = 0
            else:
                name, rank, cn, specimens = entry
                my_species, gb_species = 0, 0

            row_mm = max(5, {
                "Order": font_size + 6, "Suborder": font_size + 6,
                "Superfamily": font_size + 4, "Family": font_size + 2,
                "Subfamily": font_size + 2,
                "Genus": font_size, "Species": font_size,
            }.get(rank, font_size))

            if cumulative_mm + row_mm > PAGE_HEIGHT_MM and i > 0:
                page_break = QFrame()
                page_break.setFixedHeight(24)
                page_break.setStyleSheet(
                    "background: white; border-top: 2px dashed #c00; "
                    "border-bottom: 2px dashed #c00;"
                )
                pb_layout = QHBoxLayout(page_break)
                pb_layout.setContentsMargins(0, 2, 0, 2)
                page_num += 1
                pb_label = QLabel(f"— Page {page_num} —")
                pb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pb_label.setStyleSheet(
                    "color: #c00; font-size: 9px; font-weight: bold; "
                    "background: white; border: none;"
                )
                pb_layout.addWidget(pb_label)
                self._cl.addWidget(page_break)
                cumulative_mm = 0

            if i > 0 and cumulative_mm > 0:
                cut = QFrame()
                cut.setFixedHeight(1)
                cut.setStyleSheet("background: #ccc; margin: 0 8px;")
                self._cl.addWidget(cut)

            card = self._card(name, rank, cn, specimens, my_species, gb_species,
                              full_width, show_common,
                              show_my_specimens, show_my_species, show_fauna,
                              font_family, font_size)
            self._cl.addWidget(card)
            cumulative_mm += row_mm

        self._cl.addStretch()
        self._scroll.setWidget(self._container)

    def _card(self, name, rank, cn, specimens, my_species, gb_species,
              fw, sc, s_specimens, s_species, s_fauna, ff, fs):
        sz = max(7, fs + RANK_OFFSET.get(rank, 0))
        dsz = max(7, sz - 2)
        S = {
            "Order": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-weight:bold;"
                f"padding:6px 12px;border-top:3px solid #000;border-bottom:1px solid #000;"
            ),
            "Suborder": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-weight:bold;"
                f"padding:4px 12px;"
            ),
            "Superfamily": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-weight:bold;"
                f"padding:4px 12px;"
            ),
            "Family": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-weight:bold;"
                f"padding:4px 12px;"
            ),
            "Subfamily": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-weight:bold;"
                f"padding:4px 12px;"
            ),
            "Genus": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-style:italic;"
                f"padding:3px 12px;"
            ),
            "Species": (
                f"background:white;color:#000;font-size:{sz}px;"
                f"font-family:'{ff}';font-style:italic;"
                f"padding:3px 12px;"
            ),
        }
        card = QFrame()
        style = S.get(rank, S["Species"])
        if not fw and rank in ("Family", "Subfamily", "Genus", "Species"):
            style += "max-width:200px;"
        card.setStyleSheet(f"QFrame{{{style}}}")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        dn = name.upper() if rank in ("Order", "Suborder") else name
        nl = QLabel(dn)
        nl.setStyleSheet(
            f"border:none;background:transparent;"
            f"font-size:{sz}px;font-family:'{ff}';"
        )
        layout.addWidget(nl, 1)
        rp = []
        if sc and cn:
            rp.append(cn)
        # Build count parts based on toggles
        if rank == "Species":
            if s_specimens and specimens > 0:
                rp.append(f"{specimens} specimen{'s' if specimens != 1 else ''}")
        elif rank in ("Family", "Genus", "Subfamily"):
            parts = []
            if s_specimens and specimens > 0:
                parts.append(f"{specimens} specimens")
            if s_species and my_species > 0:
                parts.append(f"{my_species} species")
            if s_fauna and gb_species > 0:
                parts.append(f"{gb_species} GB")
            if parts:
                rp.append(" / ".join(parts))
        if rp:
            rl = QLabel(" \u00b7 ".join(rp))
            rl.setStyleSheet(
                f"border:none;background:transparent;color:#888;"
                f"font-size:{dsz}px;font-family:'{ff}';"
            )
            layout.addWidget(rl)
        return card
