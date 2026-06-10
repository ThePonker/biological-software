"""
Order Accumulation Curves Grid.

Displays mini species accumulation curves per taxonomic order,
sorted by species richness (most species-rich first), 3 per row.
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QWidget
)
from PySide6.QtCore import Signal, Qt, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

try:
    from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QAreaSeries
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from ...themes import theme


class MiniAccumulationChart(QFrame):
    """Small accumulation curve for a single order."""

    clicked = Signal(str)  # Emits order name when clicked

    def __init__(self, order_name: str, species_count: int, accent_color: str = None, parent=None):
        super().__init__(parent)
        self._order_name = order_name
        self._species_count = species_count
        self._accent_color = accent_color
        self._data = []
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()

    def mousePressEvent(self, event):
        self.clicked.emit(self._order_name)

    def _setup_ui(self):
        t = theme()
        accent = self._accent_color or t.get('success')

        self.setStyleSheet(f"""
            MiniAccumulationChart {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            MiniAccumulationChart:hover {{
                border: 1px solid {accent};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 6)
        layout.setSpacing(2)

        # Title: "Coleoptera (806 species)"
        self._title_label = QLabel(f"{self._order_name} ({self._species_count:,} species)")
        self._title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('sm')};
            color: {t.get('text_heading')};
        """)
        self._title_label.setWordWrap(True)
        self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._title_label)

        if not CHARTS_AVAILABLE:
            fallback = QLabel("Charts not available")
            fallback.setStyleSheet(f"color: {t.get('text_muted')};")
            layout.addWidget(fallback)
            return

        # Chart
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.legend().hide()
        self.chart.setMargins(QMargins(4, 4, 4, 4))

        # Line + area series
        self.line_series = QLineSeries()
        self.line_series.setColor(QColor(accent))
        pen = QPen(QColor(accent))
        pen.setWidth(2)
        self.line_series.setPen(pen)

        self.area_series = QAreaSeries(self.line_series)
        fill_color = QColor(accent)
        fill_color.setAlpha(50)
        self.area_series.setBrush(QBrush(fill_color))
        self.area_series.setPen(pen)
        self.chart.addSeries(self.area_series)

        # X Axis
        self.axis_x = QValueAxis()
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setLabelsColor(QColor(t.get('text_muted')))
        self.axis_x.setGridLineVisible(True)
        self.axis_x.setGridLineColor(QColor(t.get('border')))
        self.axis_x.setMinorGridLineVisible(False)
        self.axis_x.setTickCount(5)
        font = self.axis_x.labelsFont()
        font.setPointSize(7)
        self.axis_x.setLabelsFont(font)
        self.axis_x.setTitleVisible(False)
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.area_series.attachAxis(self.axis_x)

        # Y Axis
        self.axis_y = QValueAxis()
        self.axis_y.setLabelFormat("%d")
        self.axis_y.setLabelsColor(QColor(t.get('text_muted')))
        self.axis_y.setGridLineVisible(True)
        self.axis_y.setGridLineColor(QColor(t.get('border')))
        self.axis_y.setMinorGridLineVisible(False)
        self.axis_y.setTickCount(4)
        font_y = self.axis_y.labelsFont()
        font_y.setPointSize(7)
        self.axis_y.setLabelsFont(font_y)
        self.axis_y.setTitleVisible(False)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        self.area_series.attachAxis(self.axis_y)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(160)
        self.chart_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.chart_view)

    def set_data(self, data: list):
        """Set accumulation data. Format: [{'year': int, 'cumulative': int}, ...]"""
        if not CHARTS_AVAILABLE or not data:
            return

        self._data = data
        self.line_series.clear()

        min_year = min(d['year'] for d in data)
        max_year = max(d['year'] for d in data)
        max_species = max(d['cumulative'] for d in data)

        for point in data:
            self.line_series.append(point['year'], point['cumulative'])

        if min_year == max_year:
            self.axis_x.setRange(min_year - 1, max_year + 1)
            self.axis_x.setTickCount(3)
        else:
            self.axis_x.setRange(min_year, max_year)
            self.axis_x.setTickCount(min(max_year - min_year + 1, 6))

        if max_species > 100:
            y_max = ((max_species // 100) + 1) * 100
        elif max_species > 10:
            y_max = ((max_species // 10) + 1) * 10
        else:
            y_max = max_species + 2
        self.axis_y.setRange(0, y_max)
        self.axis_y.setTickCount(4)

    def apply_theme(self):
        t = theme()
        accent = self._accent_color or t.get('success')
        self.setStyleSheet(f"""
            MiniAccumulationChart {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            MiniAccumulationChart:hover {{
                border: 1px solid {accent};
            }}
        """)
        self._title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('sm')};
            color: {t.get('text_heading')};
        """)


class OrderAccumulationGrid(QFrame):
    """Grid of mini accumulation curves, one per taxonomic order."""

    order_clicked = Signal(str)  # Emits order name when a chart is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._charts = []
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            OrderAccumulationGrid {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Section header
        self._header = QLabel("Species Accumulation by Group")
        self._header.setStyleSheet(f"""
            font-weight: 700;
            font-size: {t.font_size('xl')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(self._header)

        # Grid container
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._grid_widget)

    def set_data(self, order_data: list):
        """Set order accumulation data.

        Args:
            order_data: List of dicts sorted by species count desc:
                [{'order': str, 'species_count': int,
                  'accumulation': [{'year': int, 'cumulative': int}, ...]}, ...]
        """
        # Clear existing charts
        for chart in self._charts:
            chart.setParent(None)
            chart.deleteLater()
        self._charts = []

        if not order_data:
            return

        t = theme()
        accent = t.get('success')


        # Set equal column stretch
        for col in range(3):
            self._grid_layout.setColumnStretch(col, 1)

        for idx, order_info in enumerate(order_data):
            order_name = order_info['order']
            species_count = order_info['species_count']
            accum_data = order_info.get('accumulation', [])

            chart = MiniAccumulationChart(
                order_name=order_name,
                species_count=species_count,
                accent_color=accent
            )
            chart.clicked.connect(self.order_clicked.emit)
            chart.setFixedHeight(220)

            if accum_data:
                chart.set_data(accum_data)

            row = idx // 3
            col = idx % 3
            self._grid_layout.addWidget(chart, row, col)
            self._charts.append(chart)

    def apply_theme(self):
        t = theme()
        self._header.setStyleSheet(f"""
            font-weight: 700;
            font-size: {t.font_size('xl')};
            color: {t.get('text_heading')};
        """)
        for chart in self._charts:
            chart.apply_theme()
