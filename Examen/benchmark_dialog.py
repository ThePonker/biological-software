"""
Examen -- the Benchmark dialog: tick the surveys that make up the Key Species benchmark.

The rows and figures come from Examen.benchmark; the summary line updates as boxes are ticked.
Save writes the choices to examen.db (refused with a message on an away machine or when
scripts\\add_report_tables.py has not been run).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from Examen import benchmark as bm
from Examen.site_analysis_view import BTN_OUTLINE, BTN_PRIMARY, TABLE_STYLE
from Examen.style import TEXT_SECONDARY
from shared.text_sizes import font_css

THIS_SURVEY = " (this survey)"      # the survey being reported is never in its own benchmark
HEADS = ["Include", "Survey", "Year", "Country", "Visits", "Type", "Status-only Key %"]


class BenchmarkDialog(QDialog):
    def __init__(self, rows, parent=None):
        """rows: Examen.benchmark.benchmark_rows (pass current= to mark the survey reported)."""
        super().__init__(parent)
        self.setWindowTitle("Key Species benchmark")
        self.resize(820, 520)
        self.rows = rows
        lay = QVBoxLayout(self)
        note = QLabel("Tick the surveys to compare. Unsaved surveys follow the default: "
                      f"{bm.DEFAULT_COUNTRY}, {bm.DEFAULT_MIN_VISITS}+ visit dates, not a "
                      "deadwood or targeted survey.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {font_css('caption')};")
        lay.addWidget(note)
        self.table = QTableWidget(len(rows), len(HEADS))
        self.table.setHorizontalHeaderLabels(HEADS)
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, r in enumerate(rows):
            tick = QTableWidgetItem()
            flags = Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            if r["pct"] is None or r.get("this_survey"):
                flags = Qt.ItemFlag.NoItemFlags      # no analysis, or the survey being reported
            tick.setFlags(flags)
            tick.setCheckState(Qt.CheckState.Checked if r["included"]
                               else Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, tick)
            cells = [r["project"] + (THIS_SURVEY if r.get("this_survey") else ""), r["survey_year"], r["country"], str(r["visits"]), r["type"],
                     "-" if r["pct"] is None else f"{r['pct']:.1f}%"]
            for j, text in enumerate(cells, start=1):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, j, item)
        self.table.itemChanged.connect(self._changed)
        lay.addWidget(self.table, 1)
        self.summary = QLabel()
        lay.addWidget(self.summary)
        btns = QHBoxLayout()
        btns.addStretch(1)
        save = QPushButton("Save")
        save.setStyleSheet(BTN_PRIMARY)
        save.clicked.connect(self._save)
        close = QPushButton("Close")
        close.setStyleSheet(BTN_OUTLINE)
        close.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(close)
        lay.addLayout(btns)
        self._changed()

    def _changed(self, *_):
        for i, r in enumerate(self.rows):
            item = self.table.item(i, 0)
            if item is not None and not r.get("this_survey"):
                r["included"] = item.checkState() == Qt.CheckState.Checked
        self.summary.setText(bm.summary_line(bm.benchmark_summary(self.rows)))

    def _save(self):
        try:
            n = bm.save_choices(self.rows)
        except bm.BenchmarkError as e:
            QMessageBox.warning(self, "Benchmark not saved", str(e))
            return
        QMessageBox.information(self, "Benchmark saved", f"{n} choice(s) saved.")
