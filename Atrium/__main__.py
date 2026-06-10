"""Atrium -- Suite Launcher for Biological Software."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from Atrium.atrium_ui import AtriumApp


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    atrium = AtriumApp()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
