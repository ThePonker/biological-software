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

from PySide6.QtWidgets import QApplication

from .planner_ui import PlannerWindow
from .planner_data import DB_PATH
from shared.text_sizes import qfont


def main():
    # Check database exists
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Make sure observatum.db is in the data/ folder.")
        sys.exit(1)

    from shared import crash_log             # data\logs\crash_curator_<month>.log
    crash_log.install("curator")
    from shared import light_scheme          # always light, even on a dark-mode PC
    from shared import ui_scale              # Interface size (Settings) before the QApplication
    ui_scale.apply_before_qapp()
    light_scheme.prepare()
    app = QApplication(sys.argv)
    light_scheme.install(app)
    from shared import gc_schedule, qt_messages
    gc_schedule.install(app)         # the cyclic collector runs from a timer, not inside Qt handlers
    qt_messages.install()
    app.setFont(qfont('caption', "Segoe UI"))
    from shared.opaque_popups import install as solid_popups
    solid_popups(app)                    # F50: solid drop-down lists (the palette's colours)
    from shared.dialog_geometry import install as remember_dialog_sizes
    remember_dialog_sizes(app)                                   # every dialog keeps its size
    import paths
    if str(paths.OBSERVATUM_DIR) not in sys.path:
        sys.path.insert(0, str(paths.OBSERVATUM_DIR))
    from src.themes import theme
    from shared.tick_style import install as green_ticks, theme_colours
    green_ticks(app, lambda: theme_colours(theme()))             # check boxes ticked in green

    window = PlannerWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
