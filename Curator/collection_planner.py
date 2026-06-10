"""
Collection Layout Planner — Entry Point

Standalone tool for planning insect collection box layouts.
Reads specimen data from observatum.db and helps allocate
families to storage boxes in systematic order.

Usage:
    python -m Collection_Organiser.collection_planner

Or via the batch file:
    run_planner.bat
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .planner_ui import PlannerWindow
from .planner_data import DB_PATH


def main():
    # Check database exists
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Make sure observatum.db is in the data/ folder.")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))

    window = PlannerWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
