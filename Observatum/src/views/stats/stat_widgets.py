"""
Stats Widget Components.

Reusable widgets for stats dashboards:
- StatCard: Metric display card
- HorizontalBarChart: Horizontal bar chart
- MonthlyActivityChart: Vertical bar chart for months
- TopFamiliesList: Top families list
- YearByYearTable: Year-by-year statistics table
- RecentSpeciesList: Recent new species list
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QAbstractItemView, QScrollArea, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ...themes import theme


class StatCard(QFrame):
    """A statistics card showing a metric."""
    
    export_clicked = Signal()
    
    def __init__(self, title: str, value: str, subtitle: str = "", 
                 color: str = None, show_export: bool = False, parent=None):
        super().__init__(parent)
        t = theme()
        
        # Use provided color or default to text_heading
        self._value_color = color or t.get('text_heading')
        
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header row
        header = QHBoxLayout()
        
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        header.addWidget(self._title_label)
        
        header.addStretch()
        
        if show_export:
            export_btn = QPushButton("Export CSV ↓")
            export_btn.setStyleSheet(f"color: {t.get('success')}; border: none; font-size: {t.font_size('sm')};")
            export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            export_btn.clicked.connect(self.export_clicked.emit)
            header.addWidget(export_btn)
        
        layout.addLayout(header)
        
        # Value
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(f"font-size: {t.font_size('stat')}; font-weight: bold; color: {self._value_color};")
        layout.addWidget(self._value_label)
        
        # Subtitle
        if subtitle:
            self._sub_label = QLabel(subtitle)
            self._sub_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
            layout.addWidget(self._sub_label)
    
    def set_value(self, value: str, subtitle: str = None):
        """Set the card value."""
        self._value_label.setText(value)
        if subtitle and hasattr(self, '_sub_label'):
            self._sub_label.setText(subtitle)
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        self._value_label.setStyleSheet(f"font-size: {t.font_size('stat')}; font-weight: bold; color: {self._value_color};")
        if hasattr(self, '_sub_label'):
            self._sub_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")


class HorizontalBarChart(QFrame):
    """Simple horizontal bar chart widget with optional scroll and clickable labels."""

    bar_clicked = Signal(str)  # Emits the label text when a bar row is clicked

    def __init__(self, title: str, scrollable: bool = False, parent=None):
        super().__init__(parent)
        t = theme()
        self._scrollable = scrollable

        self.setStyleSheet(f"""
            HorizontalBarChart {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        layout.addWidget(self._title_label)

        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(f"""
                QScrollArea {{ border: none; background: transparent; }}
                QScrollArea > QWidget > QWidget {{ background: transparent; }}
                QScrollBar:vertical {{
                    width: 6px;
                    background: transparent;
                }}
                QScrollBar::handle:vertical {{
                    background: {t.get('border')};
                    border-radius: 3px;
                    min-height: 20px;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)
            self._scroll_widget = QWidget()
            self._scroll_widget.setStyleSheet("background: transparent;")
            self._bars_layout = QVBoxLayout(self._scroll_widget)
            self._bars_layout.setSpacing(8)
            self._bars_layout.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(self._scroll_widget)
            layout.addWidget(scroll, 1)
        else:
            self._bars_layout = QVBoxLayout()
            self._bars_layout.setSpacing(12)
            layout.addLayout(self._bars_layout)
            layout.addStretch()

        self._current_color = t.get('success')

    def set_data(self, data: list, color: str = None):
        """Set bar data. Each item: {'label': str, 'value': int}"""
        t = theme()
        bar_color = color or t.get('success')
        self._current_color = bar_color
        
        while self._bars_layout.count():
            item = self._bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not data:
            return
        
        max_val = max(d['value'] for d in data)
        
        for item in data:
            row = QHBoxLayout()
            row.setSpacing(12)
            
            label = QLabel(item['label'])
            label.setFixedWidth(90)
            label_name = item['label']
            label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; text-decoration: none;")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setToolTip(f"Click to filter by {label_name}")
            label.mousePressEvent = lambda e, n=label_name: self.bar_clicked.emit(n)
            row.addWidget(label)
            
            bar_container = QFrame()
            bar_container.setFixedHeight(16)
            bar_container.setStyleSheet(f"background-color: {t.get('hover')}; border-radius: {t.get('radius_lg')};")
            bar_layout = QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            
            bar = QFrame()
            width_pct = (item['value'] / max_val * 100) if max_val > 0 else 0
            bar.setStyleSheet(f"background-color: {bar_color}; border-radius: {t.get('radius_lg')};")
            bar.setFixedHeight(16)
            bar_layout.addWidget(bar, int(width_pct))
            bar_layout.addStretch(100 - int(width_pct))
            
            row.addWidget(bar_container, 1)
            
            value_label = QLabel(str(item['value']))
            value_label.setFixedWidth(40)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            value_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('sm')};")
            row.addWidget(value_label)
            
            container = QWidget()
            container.setLayout(row)
            self._bars_layout.addWidget(container)
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            HorizontalBarChart {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")


class MonthlyActivityChart(QFrame):
    """Mini vertical bar chart for monthly activity with gridlines and clickable bars."""
    species_changed = Signal(str)
    month_clicked = Signal(int)  # Emits month number (1-12)
    MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def __init__(self, title: str, show_species_filter: bool = False, value_label: str = "records", parent=None):
        super().__init__(parent)
        self._show_species_filter = show_species_filter
        self._all_data = {}
        self._values = []
        self._value_label = value_label
        t = theme()

        self.setStyleSheet(f"""
            MonthlyActivityChart {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        layout.addWidget(self._title_label)

        # Main chart area: y-axis + bars overlay with gridlines
        chart_row = QHBoxLayout()

        # Y-axis labels container
        self._y_axis_widget = QWidget()
        self._y_axis_widget.setFixedWidth(40)
        self._y_axis_layout = QVBoxLayout(self._y_axis_widget)
        self._y_axis_layout.setContentsMargins(0, 0, 4, 0)
        self._y_axis_layout.setSpacing(0)
        chart_row.addWidget(self._y_axis_widget)

        # Bars area (stacked: gridlines behind, bars in front)
        self._bars_container = QWidget()
        self._bars_outer = QVBoxLayout(self._bars_container)
        self._bars_outer.setContentsMargins(0, 0, 0, 0)
        self._bars_outer.setSpacing(0)

        self._chart_layout = QHBoxLayout()
        self._chart_layout.setSpacing(4)
        self._bars_outer.addLayout(self._chart_layout, 1)

        chart_row.addWidget(self._bars_container, 1)

        self.setMinimumHeight(400)
        layout.addLayout(chart_row, 1)

        # Month labels
        self._labels_layout = QHBoxLayout()
        self._labels_layout.setSpacing(4)
        # Spacer to align with y-axis
        spacer = QWidget()
        spacer.setFixedWidth(44)
        self._labels_layout.addWidget(spacer)
        self._month_labels = []
        for idx, m in enumerate(self.MONTHS):
            lbl = QLabel(m)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('xs')};")
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setToolTip(f"Click to filter by {m}")
            month_num = idx + 1
            lbl.mousePressEvent = lambda e, mn=month_num: self.month_clicked.emit(mn)
            self._labels_layout.addWidget(lbl)
            self._month_labels.append(lbl)
        layout.addLayout(self._labels_layout)

        self._current_color = t.get('success_bright')

    def set_data(self, values: list, color: str = None):
        """Set monthly values (12 integers)."""
        t = theme()
        bar_color = color or t.get('success_bright')
        self._current_color = bar_color
        self._values = values

        # Clear existing bars
        while self._chart_layout.count():
            item = self._chart_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        max_val = max(values) if values else 1

        # Calculate nice tick values with finer intervals
        ticks = self._calculate_ticks(max_val)
        nice_max = ticks[-1] if ticks else max_val

        # Update Y-axis
        self._update_y_axis(ticks)

        # Build bars with gridlines
        for idx, val in enumerate(values):
            bar_container = QWidget()
            bar_container.setCursor(Qt.CursorShape.PointingHandCursor)
            bar_container.setToolTip(f"{self.MONTHS[idx]}: {val:,} {self._value_label}")
            month_num = idx + 1
            bar_container.mousePressEvent = lambda e, mn=month_num: self.month_clicked.emit(mn)

            bar_layout = QVBoxLayout(bar_container)
            bar_layout.setContentsMargins(0, 0, 0, 0)
            bar_layout.setSpacing(0)

            height_pct = (val / nice_max * 100) if nice_max > 0 else 0
            bar_layout.addStretch(100 - int(height_pct))

            bar = QFrame()
            bar.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")
            bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            bar_layout.addWidget(bar, int(height_pct))

            self._chart_layout.addWidget(bar_container)

        # Paint gridlines
        self._draw_gridlines(ticks, nice_max)

    def _calculate_ticks(self, max_val: int) -> list:
        """Calculate nice round tick values with finer intervals."""
        if max_val <= 0:
            return [0, 1]

        if max_val <= 10:
            step = 2
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 50:
            step = 10
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 100:
            step = 20
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 500:
            step = 100
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 1000:
            step = 200
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 5000:
            step = 1000
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 10000:
            step = 1000
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        elif max_val <= 50000:
            step = 5000
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))
        else:
            step = 10000
            nice_max = ((max_val // step) + 1) * step
            return list(range(0, nice_max + 1, step))

    def _update_y_axis(self, ticks: list):
        """Update Y-axis labels."""
        t = theme()

        def format_tick(val):
            if val >= 1000:
                if val % 1000 == 0:
                    return f"{val // 1000}k"
                return f"{val:,}"
            return str(val)

        # Clear old labels
        while self._y_axis_layout.count():
            item = self._y_axis_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        max_tick = max(ticks) if ticks else 1
        reversed_ticks = list(reversed(ticks))

        for i, tick in enumerate(reversed_ticks):
            lbl = QLabel(format_tick(tick))
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('xs')};")

            if i == 0:
                self._y_axis_layout.addWidget(lbl)
            else:
                prev_tick = reversed_ticks[i - 1]
                stretch = prev_tick - tick
                self._y_axis_layout.addStretch(stretch)
                self._y_axis_layout.addWidget(lbl)

    def _draw_gridlines(self, ticks: list, nice_max: int):
        """Draw horizontal gridlines across the bars area."""
        t = theme()
        grid_color = t.get('border', '#e0e0e0')

        # Remove old gridlines
        if hasattr(self, '_gridline_widgets'):
            for w in self._gridline_widgets:
                w.deleteLater()
        self._gridline_widgets = []

        if nice_max <= 0:
            return

        # We paint gridlines as thin QFrames positioned absolutely over the bars container
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._position_gridlines(ticks, nice_max, grid_color))

    def _position_gridlines(self, ticks: list, nice_max: int, grid_color: str):
        """Position gridlines after layout is settled."""
        container = self._bars_container
        h = container.height()
        if h <= 0:
            return

        # Remove previous
        if hasattr(self, '_gridline_widgets'):
            for w in self._gridline_widgets:
                w.deleteLater()
        self._gridline_widgets = []

        for tick in ticks[1:]:  # Skip 0 (bottom)
            fraction = tick / nice_max
            y_pos = int(h * (1.0 - fraction))

            line = QFrame(container)
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {grid_color};")
            line.setGeometry(0, y_pos, container.width(), 1)
            line.show()
            line.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._gridline_widgets.append(line)

    def resizeEvent(self, event):
        """Reposition gridlines on resize."""
        super().resizeEvent(event)
        if hasattr(self, '_values') and self._values:
            ticks = self._calculate_ticks(max(self._values) if self._values else 1)
            nice_max = ticks[-1] if ticks else 1
            grid_color = theme().get('border', '#e0e0e0')
            self._position_gridlines(ticks, nice_max, grid_color)

    def set_species_list(self, species_names: list):
        """Populate the species filter dropdown."""
        if not self._show_species_filter or not hasattr(self, '_species_combo'):
            return
        self._species_combo.blockSignals(True)
        self._species_combo.clear()
        self._species_combo.addItem("All Species", "")
        for name in sorted(species_names):
            if name:
                self._species_combo.addItem(name, name)
        self._species_combo.blockSignals(False)

    def _on_species_changed(self, index: int):
        """Handle species filter change."""
        if hasattr(self, '_species_combo'):
            species = self._species_combo.currentData()
            self.species_changed.emit(species or "")

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            MonthlyActivityChart {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")


class TopFamiliesList(QFrame):
    """List showing top families with counts."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        t = theme()

        self.setStyleSheet(f"""
            TopFamiliesList {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        layout.addWidget(self._title_label)

        # Scroll area for families list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {t.get('surface_alt')};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {t.get('border_strong')};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Container for list items
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)

        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

    def set_data(self, data: list):
        """Set data. Each item: {'family': str, 'species': int, 'records': int}"""
        t = theme()
        
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for item in data:
            row = QHBoxLayout()
            
            family_label = QLabel(item['family'])
            family_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
            row.addWidget(family_label)
            row.addStretch()
            
            species_label = QLabel(str(item['species']))
            species_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('sm')};")
            row.addWidget(species_label)
            
            records_label = QLabel(f"({item['records']})")
            records_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
            row.addWidget(records_label)
            
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            container.setLayout(row)
            container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._list_layout.addWidget(container)
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            TopFamiliesList {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")


class YearByYearTable(QFrame):
    """Table showing year-by-year statistics."""

    export_year_clicked = Signal(str)
    export_all_clicked = Signal()
    year_clicked = Signal(int)
    year_species_clicked = Signal(int)
    year_new_species_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()

        self.setStyleSheet(f"""
            YearByYearTable {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        self._title_label = QLabel("Year by Year")
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        header.addWidget(self._title_label)
        header.addStretch()

        export_btn = QPushButton("Export All Years CSV ↓")
        export_btn.setStyleSheet(f"color: {t.get('success')}; border: none; font-size: {t.font_size('sm')};")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self.export_all_clicked.emit)
        header.addWidget(export_btn)
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Year', 'Species', 'Records', 'New', ''])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 40)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                selection-background-color: transparent;
                selection-color: {t.get('text_primary')};
                outline: none;
            }}
            QTableWidget::item:selected {{
                background-color: transparent;
            }}
            QTableWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
            QTableWidget::item:focus {{
                background-color: transparent;
                outline: none;
                border: none;
            }}
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click - route to appropriate signal."""
        year_item = self.table.item(row, 0)
        if not year_item:
            return
        try:
            year = int(year_item.text())
        except ValueError:
            return
        if col == 1:  # Species
            self.year_species_clicked.emit(year)
        elif col == 3:  # New
            self.year_new_species_clicked.emit(year)
        elif col in (0, 2):  # Year or Records
            self.year_clicked.emit(year)

    def set_data(self, data: dict):
        """Set data. Dict of year -> {species, records, newSpecies}"""
        t = theme()
        years = sorted(data.keys(), reverse=True)
        self.table.setRowCount(len(years))

        for row, year in enumerate(years):
            stats = data[year]

            year_item = QTableWidgetItem(str(year))
            year_item.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
            year_item.setFlags(year_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, year_item)

            species_item = QTableWidgetItem(str(stats['species']))
            species_item.setFlags(species_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, species_item)

            records_item = QTableWidgetItem(str(stats['records']))
            records_item.setFlags(records_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, records_item)

            new_item = QTableWidgetItem(f"+{stats['newSpecies']}")
            new_item.setForeground(Qt.GlobalColor.darkGreen)
            new_item.setFlags(new_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 3, new_item)

            csv_btn = QPushButton("CSV")
            csv_btn.setStyleSheet(f"color: {t.get('text_muted')}; border: none; font-size: {t.font_size('xs')};")
            csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            csv_btn.clicked.connect(lambda checked, y=year: self.export_year_clicked.emit(str(y)))
            self.table.setCellWidget(row, 4, csv_btn)

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            YearByYearTable {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")


class RecentSpeciesList(QFrame):
    """List showing recently recorded new species."""
    
    view_more_clicked = Signal()
    species_clicked = Signal(str)  # Emits species name when card clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        
        self.setStyleSheet(f"""
            RecentSpeciesList {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QHBoxLayout()
        self._title_label = QLabel("Recent New Species")
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        header.addWidget(self._title_label)
        header.addStretch()
        
        view_more_btn = QPushButton("View more →")
        view_more_btn.setStyleSheet(f"color: {t.get('success')}; border: none; font-size: {t.font_size('sm')};")
        view_more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_more_btn.clicked.connect(self.view_more_clicked.emit)
        header.addWidget(view_more_btn)
        layout.addLayout(header)
        
        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(8)
        layout.addLayout(self._list_layout)
        layout.addStretch()
    
    def set_data(self, data: list):
        """Set data. Each item: {'species': str, 'date': str, 'location': str}"""
        t = theme()
        
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for item in data:
            species_name = item['species']
            card = QFrame()
            card.setObjectName("speciesCard")
            card.setStyleSheet(f"""
                QFrame#speciesCard {{
                    background-color: {t.get('surface_alt')};
                    border-radius: {t.get('radius_sm')};
                }}
                QFrame#speciesCard:hover {{
                    background-color: {t.get('hover')};
                }}
            """)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)

            info_layout = QVBoxLayout()

            species_label = QLabel(f"<i>{item['species']}</i>")
            species_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: {t.font_size('sm')};")
            species_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            info_layout.addWidget(species_label)

            location_label = QLabel(item['location'])
            location_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
            location_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            info_layout.addWidget(location_label)

            card_layout.addLayout(info_layout)
            card_layout.addStretch()

            date_label = QLabel(item['date'])
            date_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
            date_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            card_layout.addWidget(date_label)

            card.mousePressEvent = lambda e, s=species_name: self.species_clicked.emit(s)
            self._list_layout.addWidget(card)

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            RecentSpeciesList {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        self._title_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")


# ============================================================
# Centralised widgets (extracted from dashboard duplicates)
# ============================================================

try:
    from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QAreaSeries
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from PySide6.QtCore import QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

class AccumulationCurveChart(QFrame):
    """Species accumulation curve chart widget with enhanced styling."""
    
    def __init__(self, title: str = "Species Accumulation", accent_color: str = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._accent_color = accent_color
        self._data = []
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        accent = self._accent_color or t.get('success')
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        if not CHARTS_AVAILABLE:
            # Fallback if charts not available
            fallback = QLabel("Charts not available")
            fallback.setStyleSheet(f"color: {t.get('text_muted')};")
            layout.addWidget(fallback)
            return
        
        # Chart
        self.chart = QChart()
        self.chart.setBackgroundVisible(False)
        self.chart.legend().hide()
        self.chart.setMargins(QMargins(10, 10, 10, 10))
        
        # Area series for fill under line
        self.line_series = QLineSeries()
        self.line_series.setColor(QColor(accent))
        pen = QPen(QColor(accent))
        pen.setWidth(3)
        self.line_series.setPen(pen)
        
        # Create area series with gradient fill
        self.area_series = QAreaSeries(self.line_series)
        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
        gradient.setColorAt(0, QColor(accent))
        gradient.setColorAt(1, QColor(accent))
        
        fill_color = QColor(accent)
        fill_color.setAlpha(50)
        self.area_series.setBrush(QBrush(fill_color))
        self.area_series.setPen(pen)
        
        self.chart.addSeries(self.area_series)
        
        # X Axis
        self.axis_x = QValueAxis()
        self.axis_x.setLabelFormat("%d")
        self.axis_x.setTitleText("Year")
        self.axis_x.setTitleBrush(QBrush(QColor(t.get('text_secondary'))))
        self.axis_x.setLabelsColor(QColor(t.get('text_secondary')))
        self.axis_x.setGridLineVisible(True)
        self.axis_x.setGridLineColor(QColor(t.get('border')))
        self.axis_x.setMinorGridLineVisible(False)
        self.axis_x.setTickCount(10)
        self.chart.addAxis(self.axis_x, Qt.AlignBottom)
        self.area_series.attachAxis(self.axis_x)
        
        # Y Axis
        self.axis_y = QValueAxis()
        self.axis_y.setLabelFormat("%d")
        self.axis_y.setTitleText("Cumulative Species")
        self.axis_y.setTitleBrush(QBrush(QColor(t.get('text_secondary'))))
        self.axis_y.setLabelsColor(QColor(t.get('text_secondary')))
        self.axis_y.setGridLineVisible(True)
        self.axis_y.setGridLineColor(QColor(t.get('border')))
        self.axis_y.setMinorGridLineVisible(False)
        self.chart.addAxis(self.axis_y, Qt.AlignLeft)
        self.area_series.attachAxis(self.axis_y)
        
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(250)
        layout.addWidget(self.chart_view)
    
    def set_data(self, data: list):
        """Set accumulation curve data. Format: [{'year': int, 'cumulative': int}, ...]"""
        if not CHARTS_AVAILABLE:
            return
            
        self._data = data
        self.line_series.clear()
        
        if not data:
            return
        
        min_year = min(d['year'] for d in data)
        max_year = max(d['year'] for d in data)
        max_species = max(d['cumulative'] for d in data)
        
        for point in data:
            self.line_series.append(point['year'], point['cumulative'])
        
        # Set nice axis ranges
        self.axis_x.setRange(min_year, max_year)
        self.axis_x.setTickCount(min(max_year - min_year + 1, 15))
        
        # Round up max species to nice number
        y_max = ((max_species // 500) + 1) * 500 if max_species > 500 else ((max_species // 100) + 1) * 100
        self.axis_y.setRange(0, y_max)
        self.axis_y.setTickCount(6)
    
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)

class DataTable(QFrame):
    """Reusable data table widget for Order/Family breakdowns."""

    cell_clicked = Signal(int, int, str)  # row, column, cell text
    
    def __init__(self, title: str, columns: list, parent=None):
        super().__init__(parent)
        self._title = title
        self._columns = columns
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        # Table - bigger with scroll
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels(self._columns)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(180)  # Show ~5 rows
        self.table.setMaximumHeight(250)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                border: none;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QTableWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 8px;
                font-weight: 600;
            }}
        """)
        self.table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)
    
    def _on_cell_clicked(self, row: int, col: int):
        """Emit cell_clicked with the name from column 0."""
        item = self.table.item(row, 0)
        name = item.text() if item else ''
        if name:
            self.cell_clicked.emit(row, col, name)

    def set_data(self, data: list, key_field: str):
        """Set table data. data is list of dicts with key_field, 'species', 'records'."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))

        for row, item in enumerate(data):
            name_item = QTableWidgetItem(str(item.get(key_field, '')))
            self.table.setItem(row, 0, name_item)

            species_val = item.get('species', 0)
            species_item = QTableWidgetItem()
            species_item.setData(Qt.ItemDataRole.DisplayRole, int(species_val))
            species_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, species_item)

            records_val = item.get('records', 0)
            records_item = QTableWidgetItem()
            records_item.setData(Qt.ItemDataRole.DisplayRole, int(records_val))
            records_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, records_item)

        self.table.setSortingEnabled(True)

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)

