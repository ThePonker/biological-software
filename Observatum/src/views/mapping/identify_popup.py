"""The Mapping tab's Identify tool, the tab's half (25 Oct 2026): the pop-up and its controller.

The Identify button (toolbar.py) puts GridMap in Identify mode; a click then comes here as
identify_requested(e, n, global_pos). build_info() gathers what is at the point (grid references,
vice county, the records of the square, and what the ticked layers hold: GridMap.identify_at) and
IdentifyPopup shows it in a small frameless panel at the click. It closes on Esc, on its close button (top right), when Identify is
turned off, and a new click moves it. Colours and sizes come from theme(). Display only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QPoint, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from shared.osgb import en_to_gridref
from ...themes import theme

REF_DIGITS = (("10 km", 2), ("1 km", 4), ("100 m", 6))


@dataclass
class IdentifyInfo:
    """What is at one point (OSGB metres)."""
    e: float
    n: float
    refs: List[Tuple[str, str]] = field(default_factory=list)   # [("10 km", "SP43"), ...]
    vc: str = ""                # "VC23 Oxfordshire", or why there is none
    vc_note: str = ""           # e.g. "On the VC34/VC35 boundary: VC34 46%, VC35 54%"
    square: Optional[str] = None
    count: int = 0              # the records of the recorded square under the point
    layers: List[Tuple[str, str]] = field(default_factory=list)  # (layer label, feature name / class / value)
    details: List[dict] = field(default_factory=list)   # GridMap.identify_details: label, items (text, details, link)


def build_info(map_widget, e: float, n: float, squares: Dict[str, dict], vc_service) -> IdentifyInfo:
    """Gather everything the pop-up shows. `squares`: the map's squares (label -> dict with
    'count'); `vc_service`: a VCLookupService (or None/failing: the VC line says so)."""
    info = IdentifyInfo(e, n)
    info.refs = [(name, en_to_gridref(e, n, d) or "-") for name, d in REF_DIGITS]
    ref100 = info.refs[-1][1]
    try:
        res = vc_service.assess(ref100) if vc_service is not None and ref100 != "-" else None
    except Exception as ex:                     # a missing or unreadable VC database
        print(f"[Identify] vice county not looked up: {ex}")
        res = None
    if res:
        info.vc = f"VC{res['vc_number']} {res.get('vc_name') or ''}".strip()
        info.vc_note = res.get("note") or ""
    else:
        info.vc = "none found"
    label = map_widget.square_label_at(e, n)
    if label and label in squares:
        info.square = label
        info.count = int(squares[label].get("count", 0) or 0)
    info.layers = map_widget.identify_at(e, n)
    if hasattr(map_widget, "identify_details"):
        info.details = map_widget.identify_details(e, n)
    return info


class IdentifyPopup(QFrame):
    """A small frameless panel showing an IdentifyInfo. Esc closes it."""

    open_records = Signal(str)          # the square's label ("Open records")

    def __init__(self, info: IdentifyInfo, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("identifyPopup")
        self.info = info
        t = theme()
        self.setStyleSheet(
            f"QFrame#identifyPopup {{ background-color: {t.get('surface')}; "
            f"border: 1px solid {t.get('border_strong')}; border-radius: {t.get('radius_sm')}; }}"
            f"QLabel {{ color: {t.get('text_primary')}; font-size: {t.get('font_size_sm')}pt; "
            f"border: none; background: transparent; }}"
            f"QLabel#muted {{ color: {t.get('text_secondary')}; }}"
            f"QPushButton {{ border: 1px solid {t.get('border')}; border-radius: {t.get('radius_sm')}; "
            f"padding: 1px 8px; color: {t.get('text_heading')}; background: {t.get('surface')}; "
            f"font-size: {t.get('font_size_sm')}pt; }}"
            f"QPushButton:hover {{ background-color: {t.get('hover')}; }}"
            f"QPushButton#closeBtn {{ background-color: transparent; color: {t.get('text_secondary')}; "
            f"border: 1px solid {t.get('border')}; padding: 0; min-width: 20px; max-width: 20px; "
            f"min-height: 20px; max-height: 20px; }}"
            f"QPushButton#closeBtn:hover {{ background-color: {t.get('hover')}; }}"
            f"QPushButton#link {{ border: none; padding: 0; color: {t.get('primary')}; "
            f"text-decoration: underline; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        self.close_btn = QPushButton("\u2715")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setAutoDefault(False)
        self.close_btn.clicked.connect(self.close)
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(self.close_btn)
        lay.addLayout(top)
        self.ref_labels: List[QLabel] = []
        for i, (name, ref) in enumerate(info.refs):
            row = QHBoxLayout()
            row.setSpacing(8)
            lab = QLabel(f"{name}: {ref}")
            self.ref_labels.append(lab)
            row.addWidget(lab)
            row.addStretch()
            if i == len(info.refs) - 1:
                self.copy_btn = QPushButton("Copy")
                self.copy_btn.setToolTip("Copy the 100 m grid reference")
                self.copy_btn.clicked.connect(self.copy_ref)
                row.addWidget(self.copy_btn)
            lay.addLayout(row)
        self.vc_label = QLabel(f"Vice county: {info.vc}")
        lay.addWidget(self.vc_label)
        self.note_label = None
        if info.vc_note:
            self.note_label = QLabel(info.vc_note)
            self.note_label.setObjectName("muted")
            self.note_label.setWordWrap(True)
            self.note_label.setMaximumWidth(280)
            lay.addWidget(self.note_label)
        rec = QHBoxLayout()
        rec.setSpacing(8)
        self.records_label = QLabel(f"Records here: {info.count}" if info.count else "No records here")
        rec.addWidget(self.records_label)
        self.open_btn = None
        if info.count and info.square:
            self.open_btn = QPushButton("Open records")
            self.open_btn.setObjectName("link")
            self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.open_btn.clicked.connect(lambda: self.open_records.emit(info.square))
            rec.addWidget(self.open_btn)
        rec.addStretch()
        lay.addLayout(rec)
        self.layer_labels: List[QLabel] = []
        self.detail_labels: List[QLabel] = []
        self.link_buttons: List[QPushButton] = []
        if info.details:
            for group in info.details:
                for item in group.get("items", ()):
                    self._add_item(lay, group.get("label", ""), item)
        else:
            for label, name in info.layers:
                self._add_layer_label(lay, f"{label}: {name}" if name else label)
        self._esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc.setContext(Qt.ShortcutContext.WindowShortcut)
        self._esc.activated.connect(self.close)

    def _add_layer_label(self, lay, text: str):
        lab = QLabel(text)
        lab.setWordWrap(True)           # a long rock-unit or habitat name wraps
        lab.setMaximumWidth(320)
        self.layer_labels.append(lab)
        lay.addWidget(lab)

    def _add_item(self, lay, label: str, item: dict):
        """One feature: "<short>: <text>", its detail lines (muted, smaller, wrapping) and, with a
        link, an "Open site page" button."""
        text = item.get("text") or ""
        self._add_layer_label(lay, f"{label}: {text}" if text else label)
        details = item.get("details") or ()
        if details:
            lab = QLabel(" \u00b7 ".join(f"{k} {v}" for k, v in details))
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lab.setMaximumWidth(320)
            lab.setStyleSheet(f"font-size: {theme().get('font_size_xs')}pt;")
            self.detail_labels.append(lab)
            lay.addWidget(lab)
        url = item.get("link")
        if url:
            btn = QPushButton("Open site page")
            btn.setObjectName("link")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(url)
            btn.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            self.link_buttons.append(btn)
            row = QHBoxLayout()
            row.addWidget(btn)
            row.addStretch()
            lay.addLayout(row)

    def copy_ref(self):
        """Copy the 100 m grid reference to the clipboard."""
        QGuiApplication.clipboard().setText(self.info.refs[-1][1])

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(ev)

    def show_at(self, global_pos: QPoint):
        """Show beside the click, kept on the screen."""
        self.adjustSize()
        pos = QPoint(global_pos.x() + 12, global_pos.y() + 12)
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            pos.setX(max(g.left(), min(pos.x(), g.right() - self.width())))
            pos.setY(max(g.top(), min(pos.y(), g.bottom() - self.height())))
            if pos.y() < global_pos.y() + 12 and global_pos.y() - self.height() - 12 >= g.top():
                pos.setY(global_pos.y() - self.height() - 12)   # no room below: above the click
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()


class IdentifyController(QObject):
    """Joins the toolbar's Identify button, the map and the pop-up. `squares`: a callable giving
    the map's current squares; `vc_service`: a VCLookupService, or None to make one on first use."""

    def __init__(self, map_widget, toolbar, squares: Callable[[], Dict[str, dict]],
                 parent=None, vc_service=None):
        super().__init__(parent)
        self._map, self._squares, self._vc = map_widget, squares, vc_service
        self._popup: Optional[IdentifyPopup] = None
        toolbar.identify_toggled.connect(self.set_active)
        map_widget.identify_requested.connect(self.identify)
        # Esc closes the pop-up from the map too (after a click the map, not the pop-up, has focus)
        self._map_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), map_widget)
        self._map_esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._map_esc.activated.connect(self.close_popup)

    def popup(self) -> Optional[IdentifyPopup]:
        return self._popup if self._popup is not None and self._popup.isVisible() else None

    def set_active(self, on: bool):
        self._map.set_identify_mode(on)
        if not on:
            self.close_popup()

    def close_popup(self):
        if self._popup is not None:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None

    def _vc_service(self):
        if self._vc is None:
            try:
                from ...services.vc_lookup_service import VCLookupService
                self._vc = VCLookupService()
            except Exception as ex:
                print(f"[Identify] no vice-county service: {ex}")
        return self._vc

    def identify(self, e: float, n: float, global_pos: QPoint):
        """A click in Identify mode: (re)open the pop-up for this point."""
        self.close_popup()
        info = build_info(self._map, e, n, self._squares(), self._vc_service())
        self._popup = IdentifyPopup(info, self._map.window())
        self._popup.open_records.connect(self._open_records)
        self._popup.show_at(global_pos)

    def _open_records(self, label: str):
        """What clicking that square does: select it and report it (the tab opens its records)."""
        self.close_popup()
        self._map.set_selected(label)
        self._map.square_clicked.emit(label)
