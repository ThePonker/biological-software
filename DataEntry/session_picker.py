"""SessionPickerPage -- the setup screen that sets the sticky session header once.

Sources type-ahead lists distinct-from-DB (site/recorder/determiner) and methods from
Observatum's DV_METHOD (with fallback). Emits a SessionHeader on Start. No writes.

Standalone-first: takes a sqlite connection for seeding; no Observatum main-window deps.
VC is manual here -- grid-ref auto-derivation lands in a later step (per 26 §7 ordering).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QGroupBox, QScrollArea, QSizePolicy,
)

from DataEntry import theme
from DataEntry.db_probe import distinct_values
from DataEntry.session_header import SessionHeader, parse_date, load_methods


def _editable_combo(values, placeholder="") -> QComboBox:
    cb = QComboBox()
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # free text allowed, not auto-added
    cb.addItem("")
    for v in values:
        cb.addItem(str(v))
    cb.setCurrentText("")
    if placeholder:
        cb.lineEdit().setPlaceholderText(placeholder)
    cb.completer().setCompletionMode(cb.completer().CompletionMode.PopupCompletion)
    cb.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    return cb


class SessionPickerPage(QWidget):
    """Collects the sticky header. Emits session_started(SessionHeader)."""

    session_started = Signal(object)

    def __init__(self, conn: Optional[sqlite3.Connection], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._conn = conn
        self._methods, self._methods_source = load_methods()
        self._build_ui()

    # -- data sourcing ---------------------------------------------------
    def _distinct(self, column: str) -> list:
        if self._conn is None:
            return []
        return distinct_values(self._conn, column)

    # -- ui --------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)

        body = QWidget()
        body.setStyleSheet(f"background: {theme.PAPER};")
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(12)

        intro = QLabel("New session \u2014 set what stays the same for this sitting. Every field "
                       "can be overridden per record later.")
        intro.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        intro.setWordWrap(True)
        v.addWidget(intro)

        # Core form
        core = QGroupBox("Session header")
        core.setStyleSheet(self._group_qss())
        form = QFormLayout(core)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Personal", "Commercial"])
        self.cmb_mode.currentTextChanged.connect(self._on_mode_changed)
        form.addRow(self._lbl("Mode"), self.cmb_mode)

        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("today \u00b7 yesterday \u00b7 2026-07-06 \u00b7 06/07/2026")
        self.txt_date.textChanged.connect(self._on_date_changed)
        self.lbl_date_preview = QLabel("")
        self.lbl_date_preview.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        drow = QVBoxLayout()
        drow.setSpacing(2)
        drow.addWidget(self.txt_date)
        drow.addWidget(self.lbl_date_preview)
        dwrap = QWidget(); dwrap.setLayout(drow)
        form.addRow(self._lbl("Date"), dwrap)

        self.cmb_site = _editable_combo(self._distinct("site_name"), "type or pick a site")
        form.addRow(self._lbl("Site"), self.cmb_site)

        self.txt_grid = QLineEdit()
        self.txt_grid.setPlaceholderText("e.g. SP5106")
        form.addRow(self._lbl("Grid ref"), self.txt_grid)

        self.txt_vc = QLineEdit()
        self.txt_vc.setPlaceholderText("(auto-derives from grid ref in a later step)")
        form.addRow(self._lbl("Vice county"), self.txt_vc)

        self.cmb_recorder = _editable_combo(self._distinct("recorder"), "recorder")
        self.cmb_recorder.currentTextChanged.connect(self._on_recorder_changed)
        form.addRow(self._lbl("Recorder"), self.cmb_recorder)

        self.cmb_determiner = _editable_combo(self._distinct("determiner"), "defaults to recorder")
        form.addRow(self._lbl("Determiner"), self.cmb_determiner)

        self.cmb_method = QComboBox()
        self.cmb_method.setEditable(True)
        self.cmb_method.addItem("")
        for m in self._methods:
            self.cmb_method.addItem(str(m))
        form.addRow(self._lbl("Method"), self.cmb_method)
        self.lbl_method_src = QLabel(f"methods: {self._methods_source}")
        self.lbl_method_src.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px;")
        form.addRow("", self.lbl_method_src)

        self.txt_stage = QLineEdit("Adult")
        form.addRow(self._lbl("Stage default"), self.txt_stage)

        v.addWidget(core)

        # Internal survey axes
        axes = QGroupBox("Survey structure (internal \u2014 not sent to iRecord)")
        axes.setStyleSheet(self._group_qss())
        af = QFormLayout(axes)
        af.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        af.setSpacing(8)
        self.txt_parcel = QLineEdit(); self.txt_parcel.setPlaceholderText("parcel / sub-location")
        self.txt_trap = QLineEdit(); self.txt_trap.setPlaceholderText("trap number")
        self.txt_visit = QLineEdit(); self.txt_visit.setPlaceholderText("visit number")
        af.addRow(self._lbl("Sub-location"), self.txt_parcel)
        af.addRow(self._lbl("Trap number"), self.txt_trap)
        af.addRow(self._lbl("Visit number"), self.txt_visit)
        v.addWidget(axes)

        # Commercial-only group (hidden unless Commercial)
        self.grp_commercial = QGroupBox("Commercial")
        self.grp_commercial.setStyleSheet(self._group_qss())
        cf = QFormLayout(self.grp_commercial)
        cf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        cf.setSpacing(8)
        self.txt_project = QLineEdit()
        self.txt_client = QLineEdit()
        self.txt_embargo = QLineEdit(); self.txt_embargo.setPlaceholderText("embargo until (yyyy-mm-dd, optional)")
        cf.addRow(self._lbl("Project"), self.txt_project)
        cf.addRow(self._lbl("Client"), self.txt_client)
        cf.addRow(self._lbl("Embargo"), self.txt_embargo)
        self.grp_commercial.setVisible(False)
        v.addWidget(self.grp_commercial)

        # Validation + start
        self.lbl_validation = QLabel("")
        self.lbl_validation.setStyleSheet(f"color: {theme.CLAY}; font-size: 12px;")
        self.lbl_validation.setWordWrap(True)
        v.addWidget(self.lbl_validation)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_start = QPushButton("Start session  \u2192")
        self.btn_start.setStyleSheet(
            f"background: {theme.MOSS}; color: {theme.PAPER}; font-weight: 600;"
            f"padding: 8px 18px; border: none; border-radius: 5px;"
        )
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_start.setDefault(True)
        btn_row.addWidget(self.btn_start)
        v.addLayout(btn_row)
        v.addStretch(1)

    # -- helpers ---------------------------------------------------------
    def _lbl(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        return lab

    def _group_qss(self) -> str:
        return (
            f"QGroupBox {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f"  border-radius: 6px; margin-top: 8px; font-size: 12px; font-weight: 700;"
            f"  color: {theme.SLATE}; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}"
        )

    # -- behaviour -------------------------------------------------------
    def _on_mode_changed(self, mode: str):
        self.grp_commercial.setVisible(mode.strip().lower() == "commercial")

    def _on_date_changed(self, text: str):
        iso, raw = parse_date(text)
        if iso:
            self.lbl_date_preview.setText(f"\u2192 {iso}")
            self.lbl_date_preview.setStyleSheet(f"color: {theme.MOSS}; font-size: 11px;")
        elif raw:
            self.lbl_date_preview.setText(f"kept as typed: \u201c{raw}\u201d (not a concrete date)")
            self.lbl_date_preview.setStyleSheet(f"color: {theme.GOLD}; font-size: 11px;")
        else:
            self.lbl_date_preview.setText("")

    def _on_recorder_changed(self, text: str):
        # Determiner defaults to recorder while determiner is untouched/blank.
        if not self.cmb_determiner.currentText().strip():
            self.cmb_determiner.setCurrentText(text)

    def build_header(self) -> SessionHeader:
        iso, raw = parse_date(self.txt_date.text())
        recorder = self.cmb_recorder.currentText().strip()
        determiner = self.cmb_determiner.currentText().strip() or recorder
        return SessionHeader(
            mode=self.cmb_mode.currentText().strip(),
            date=iso, date_raw=raw,
            site_name=self.cmb_site.currentText().strip(),
            grid_ref=self.txt_grid.text().strip(),
            vice_county=self.txt_vc.text().strip(),
            recorder=recorder,
            determiner=determiner,
            method=self.cmb_method.currentText().strip(),
            stage_default=self.txt_stage.text().strip() or "Adult",
            sub_location=self.txt_parcel.text().strip(),
            trap_number=self.txt_trap.text().strip(),
            visit_number=self.txt_visit.text().strip(),
            project_name=self.txt_project.text().strip(),
            client=self.txt_client.text().strip(),
            embargo_until=self.txt_embargo.text().strip(),
        )

    def _validate(self, h: SessionHeader):
        missing = []
        if not (h.date or h.date_raw):
            missing.append("date")
        if not h.site_name:
            missing.append("site")
        if not h.recorder:
            missing.append("recorder")
        if not h.method:
            missing.append("method")
        if h.is_commercial() and not h.project_name:
            missing.append("project (commercial)")
        return missing

    def _on_start(self):
        h = self.build_header()
        missing = self._validate(h)
        if missing:
            self.lbl_validation.setText("Please set: " + ", ".join(missing) + ".")
            return
        self.lbl_validation.setText("")
        self.session_started.emit(h)
