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
import src.startup_timing  # noqa: F401  (starts the startup clock)

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
    # Home's figures, then the Recording Scheme records in the background
    if hasattr(window, "load_after_show"):
        window.load_after_show()


def main():
    from src.startup_timing import timer
    timing = timer()

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
    timing.mark("splash shown")

    # Database paths
    main_db_path = str(paths.OBSERVATUM_DB)
    uksi_db_path = str(paths.UKSI_DB)

    splash.set_progress(10, "Loading configuration...")

    # Import main window
    from src.views.main_window import MainWindow
    timing.mark("main window imported")

    splash.set_progress(30, "Creating main window...")

    # Create window with splash for progress updates
    window = MainWindow(
        main_db_path=main_db_path,
        uksi_db_path=uksi_db_path,
        splash=splash
    )
    timing.mark("main window built")

    # Startup speed (11 Oct 2026): the window no longer waits for the Recording Scheme
    # records, nor reads the Recording Scheme / Insect Collection records while hidden.
    # Those tabs read their records when first opened (MainWindow._on_tab_changed); the
    # Recording Scheme records start loading in the background once the window is up,
    # and a load that fails is reported when the tab is opened.
    splash.set_progress(100, "Ready!")
    app.processEvents()

    def show():
        finish_and_show(splash, window)
        timing.mark("window shown")

        def idle():
            timing.mark("idle (startup work done)")
        # after the post-show timers (filters 200 ms, Home fill)
        QTimer.singleShot(250, lambda: QTimer.singleShot(0, idle))
    QTimer.singleShot(0, show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
