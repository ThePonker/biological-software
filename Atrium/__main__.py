"""Atrium -- Suite Launcher for Biological Software."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from Atrium.atrium_ui import AtriumApp
from Atrium.single_instance import SingleInstance


def main():
    from shared import crash_log             # data\logs\crash_atrium_<month>.log
    crash_log.install("atrium")
    from shared import light_scheme          # always light, even on a dark-mode PC
    from shared import ui_scale              # Interface size (Settings) before the QApplication
    ui_scale.apply_before_qapp()
    light_scheme.prepare()
    app = QApplication(sys.argv)
    light_scheme.install(app)
    from shared import gc_schedule, qt_messages
    gc_schedule.install(app)         # the cyclic collector runs from a timer, not inside Qt handlers
    qt_messages.install()
    from shared.dialog_geometry import install as remember_dialog_sizes
    remember_dialog_sizes(app)                                   # every dialog keeps its size
    from Atrium.process_manager import _theme
    from shared.opaque_popups import install as solid_popups
    from shared.tick_style import install as green_ticks, theme_colours
    if _theme is not None:
        t = _theme
        solid_popups(app, lambda: (t().get('surface'), t().get('text_primary')))   # F50: solid drop-down lists
        green_ticks(app, lambda: theme_colours(t()))                                # check boxes ticked in green
    else:
        solid_popups(app)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    # One copy only (L28): if Atrium is already open, bring it to the front and stop
    instance = SingleInstance()
    if instance.signal_running_copy():
        sys.exit(0)
    atrium = AtriumApp()
    instance.listen(atrium.bring_to_front)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
