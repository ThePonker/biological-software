"""Launch the Codex Manager application."""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from .codex_manager import CodexManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Codex Manager")
    window = CodexManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
