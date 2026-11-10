"""Launch the Codex Manager application."""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from .codex_manager import CodexManager


def main():
    from shared import crash_log             # data\logs\crash_codex_<month>.log
    crash_log.install("codex")
    from shared import light_scheme          # always light, even on a dark-mode PC
    from shared import ui_scale              # Interface size (Settings) before the QApplication
    ui_scale.apply_before_qapp()
    light_scheme.prepare()
    app = QApplication(sys.argv)
    light_scheme.install(app)
    from shared import gc_schedule, qt_messages
    gc_schedule.install(app)         # the cyclic collector runs from a timer, not inside Qt handlers
    qt_messages.install()
    app.setApplicationName("Codex Manager")
    from shared.opaque_popups import install as solid_popups
    from . import theme
    solid_popups(app, lambda: (theme.SURFACE, theme.TEXT_PRIMARY))   # F50: solid drop-down lists
    from shared.dialog_geometry import install as remember_dialog_sizes
    remember_dialog_sizes(app)                                   # every dialog keeps its size
    window = CodexManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
