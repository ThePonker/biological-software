"""Home > "Year list" (Round 20, replaces Notable records): the Personal year list month by month.
A chart (year_list_chart) and three figures: species this year, last year by this date, best month.
The data is home_data.year_list, read off the GUI thread; it counts as the Personal Quick Stats
card does, so the last point of the chart is the card's "This Year Species"."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.text_sizes import font_css
from . import home_data as hd
from .card import Card
from .home_widgets import note_label
from .home_worker import JobRunner
from .year_list_chart import MONTHS, YearListChart
from ...themes import theme


class YearListCard(Card):
    def __init__(self, parent=None):
        super().__init__("Year list", parent)
        self._db_path = None
        self._jobs = JobRunner(self)
        self.add_widget(note_label("Species on your Personal year list, by the end of each month"))
        self.chart = YearListChart()
        self.add_widget(self.chart)
        self._main_layout.setStretchFactor(self.chart, 1)
        self.legend = QLabel("")
        self.legend.setWordWrap(True)
        self.add_widget(self.legend)
        figures = QHBoxLayout()
        figures.setSpacing(12)
        self.this_value = self._figure(figures)
        self.last_value = self._figure(figures)
        self.best_value = self._figure(figures)
        self.add_layout(figures)
        self.note = note_label("")
        self.note.setVisible(False)
        self.add_widget(self.note)
        self._data = None
        self._style()
        self.show_data(None)

    def _figure(self, row: QHBoxLayout) -> QLabel:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        caption, value = QLabel(), QLabel("–")
        caption.setWordWrap(True)
        lay.addWidget(caption)
        lay.addWidget(value)
        lay.addStretch()
        row.addWidget(box, 1)
        value.caption = caption
        return value

    def _style(self):
        t = theme()
        base = "border: none; background: transparent;"
        for v in (self.this_value, self.last_value, self.best_value):
            v.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('heading')};"
                            f" font-weight: 600; {base}")
            v.caption.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')}; {base}")
        self.legend.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')}; {base}")

    def set_database(self, db_path):
        self._db_path = db_path

    def reload(self, *_a):
        if not self._db_path:
            return
        path = self._db_path
        self._jobs.start(lambda: hd.year_list(path), self.show_data)

    def show_data(self, data):
        """Draw a year_list result (None: empty)."""
        self._data = data
        d = data or {"year": hd.date.today().year, "this": [None] * 12, "last": [None] * 12,
                     "total": 0, "last_by_date": 0, "best": None, "unplaced": 0}
        self.chart.set_data(d["this"], d["last"])
        t = theme()
        self.legend.setText(f"<span style='color:{t.get('primary')}'>&#9644;</span> {d['year']}"
                            f" &nbsp; <span style='color:{t.get('secondary')}'>&#9644;</span> {d['year'] - 1}")
        self.this_value.caption.setText("Species this year")
        self.this_value.setText(f"{d['total']:,}")
        self.last_value.caption.setText("Last year by this date")
        self.last_value.setText(f"{d['last_by_date']:,}")
        self.best_value.caption.setText("Best month")
        best = d["best"]
        self.best_value.setText(f"{MONTHS[best[0] - 1]} (+{best[1]:,})" if best else "–")
        self.note.setVisible(bool(d["unplaced"]))
        if d["unplaced"]:
            n = d["unplaced"]
            self.note.setText(f"{n:,} species dated by year only (or a date range): counted in the latest point")

    def apply_theme(self):
        super().apply_theme()
        self._style()
        self.show_data(self._data)
        self.chart.update()
