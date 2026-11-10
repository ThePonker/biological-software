"""
Standalone Gamification Window Launcher
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parent))  # root for paths
import paths  # noqa: F401  (sets up the suite paths)

from PySide6.QtWidgets import QApplication
from src.features.gamification import GamificationWindow, ensure_gamification_db

def main():
    ensure_gamification_db()
    
    from shared import crash_log             # data\logs\crash_game_<month>.log
    crash_log.install("game")
    from shared import light_scheme          # always light, even on a dark-mode PC
    light_scheme.prepare()
    app = QApplication(sys.argv)
    light_scheme.install(app)
    app.setApplicationName("Observatum Achievements")
    
    window = GamificationWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
