"""
Observatum V2 Main Entry Point with Splash Screen.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parent))  # Biological Software root
import paths

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer, QSettings


def apply_filter_settings(window):
    """Apply filter visibility settings after window is fully shown."""
    from src.core.config import Settings, Defaults
    settings = QSettings()
    
    # Observation tab
    show_obs = settings.value(Settings.FILTERS_VISIBLE_OBSERVATIONS, Defaults.FILTERS_VISIBLE_OBSERVATIONS, type=bool)
    if show_obs:
        window.observation_tab.filter_bar.setVisible(True)
        window.observation_tab.toolbar.filter_btn.setChecked(True)
    
    # Recording Scheme tab
    show_scheme = settings.value(Settings.FILTERS_VISIBLE_RECORDING_SCHEME, Defaults.FILTERS_VISIBLE_RECORDING_SCHEME, type=bool)
    if show_scheme:
        window.recording_scheme_tab.filter_bar.setVisible(True)
        window.recording_scheme_tab.toolbar.filter_btn.setChecked(True)
    
    # Insect Collection tab
    show_coll = settings.value(Settings.FILTERS_VISIBLE_COLLECTION, Defaults.FILTERS_VISIBLE_COLLECTION, type=bool)
    if show_coll:
        window.insect_collection_tab.filters.setVisible(True)
        window.insect_collection_tab.toolbar.filter_btn.setChecked(True)


def finish_and_show(splash, window):
    """Finish splash and show window maximized."""
    splash.close()
    window.showMaximized()
    window.connect_tab_signal()
    # Apply filter settings after a delay
    QTimer.singleShot(200, lambda: apply_filter_settings(window))


def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Observatum V2")
    app.setOrganizationName("Observatum")

    # Show splash screen immediately
    from src.views.splash_screen import ObservatumSplashScreen
    splash = ObservatumSplashScreen()
    splash.show()
    app.processEvents()

    # Database paths
    base_path = Path(__file__).parent.parent
    main_db_path = str(paths.OBSERVATUM_DB)
    uksi_db_path = str(paths.UKSI_DB)

    splash.set_progress(10, "Loading configuration...")


    # Import main window
    from src.views.main_window import MainWindow

    splash.set_progress(30, "Creating main window...")

    # Create window with splash for progress updates
    window = MainWindow(
        main_db_path=main_db_path,
        uksi_db_path=uksi_db_path,
        splash=splash
    )
    
    splash.set_progress(90, "Loading recording scheme data...")

    # Wait for RS background worker to finish before showing window
    def check_and_show():
        rs_tab = window.recording_scheme_tab
        worker = getattr(rs_tab, '_data_worker', None)
        if worker and hasattr(worker, 'results_ready') and not worker.results_ready.is_set():
            # Still loading - update splash and check again
            app.processEvents()
            QTimer.singleShot(100, check_and_show)
            return
        # Worker done (or no worker) - initialize RS with pre-loaded data
        splash.set_progress(95, "Preparing interface...")
        app.processEvents()
        # Trigger RS initialize so proxy connects while window is hidden
        rs_tab.initialize(main_db_path, uksi_db_path)
        # Also initialize IC tab while hidden (it's fast - 0.65s)
        window.insect_collection_tab.initialize(main_db_path, uksi_db_path)
        window._initialized_tabs.add(2)  # RS
        window._initialized_tabs.add(3)  # IC
        splash.set_progress(100, "Ready!")
        app.processEvents()
        QTimer.singleShot(200, lambda: finish_and_show(splash, window))

    check_and_show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
