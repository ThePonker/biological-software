"""
Collection Planner — Main Window

Tab-based window with two views:
- Taxonomic Labels (default) — tree view + label printing
- Box Layout (experimental) — visual box allocation

The Labels view is the primary workflow. Box Layout is preserved
for future development.
"""

from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QFont

from .planner_labels_view import LabelsView
from .planner_box_view import BoxLayoutView


class PlannerWindow(QMainWindow):
    """Main window for the Collection Layout Planner."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collection Layout Planner")
        self.setMinimumSize(950, 600)

        tabs = QTabWidget()
        tabs.setFont(QFont("Segoe UI", 10))

        # Default tab: Taxonomic Labels
        self.labels_view = LabelsView()
        tabs.addTab(self.labels_view, "Taxonomic Labels")

        # Experimental tab: Box Layout
        self.box_view = BoxLayoutView()
        tabs.addTab(self.box_view, "Box Layout (Experimental)")

        self.setCentralWidget(tabs)
