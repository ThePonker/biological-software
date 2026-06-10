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
    window = MuniaWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
