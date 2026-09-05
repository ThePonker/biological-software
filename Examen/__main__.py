"""Examen — Species Assessment Tool"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Also add Observatum to path for shared repositories
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Observatum"))
import paths

from PySide6.QtWidgets import QApplication

from .examen_ui import ExamenWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Examen")
    window = ExamenWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
else:
    main()
