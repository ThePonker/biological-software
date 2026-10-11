"""Atrium -- Suite Launcher for Biological Software."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from Atrium.atrium_ui import AtriumApp
from Atrium.single_instance import SingleInstance


def main():
    app = QApplication(sys.argv)
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
