"""Munia — Workload Capacity Manager.

Launch: python -m Munia
"""

import sys
from pathlib import Path

# Add project root so `import paths` resolves
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication  # noqa: E402
from Munia.munia_ui import MuniaWindow  # noqa: E402


def main():
    app = QApplication(sys.argv)
    from shared.dialog_geometry import install as remember_dialog_sizes
    remember_dialog_sizes(app)                                   # every dialog keeps its size
    from Munia.theme import _theme
    from shared.opaque_popups import install as solid_popups
    from shared.calendar_style import install as themed_calendars
    from shared.tick_style import install as green_ticks, theme_colours
    if _theme is not None:
        t = _theme
        solid_popups(app, lambda: (t().get('surface'), t().get('text_primary')))   # F50: solid drop-down lists
        themed_calendars(app, lambda: t().calendar_colours())                       # F76: readable date calendars
        green_ticks(app, lambda: theme_colours(t()))                                # check boxes ticked in green
    else:
        solid_popups(app)
    window = MuniaWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
