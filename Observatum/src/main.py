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

    # Show splash screen immediately; its bar follows the startup steps
    # (src/views/splash_progress.py) and keeps moving while records load in threads
    from src.views.splash_screen import ObservatumSplashScreen
    from src.views.splash_progress import ProgressPlan, load_seconds, save_seconds
    splash = ObservatumSplashScreen()
    kept_seconds = load_seconds()            # this computer's step durations, if known
    plan = ProgressPlan(seconds=kept_seconds)
    splash.show()
    splash.start_plan(plan)
    app.processEvents()
    timing.mark("splash shown")

    # Database paths
    main_db_path = str(paths.OBSERVATUM_DB)
    uksi_db_path = str(paths.UKSI_DB)

    splash.begin_step("imports")
    from src.views.main_window import MainWindow
    timing.mark("main window imported")

    # Create window with splash for progress updates
    splash.begin_step("window")
    window = MainWindow(
        main_db_path=main_db_path,
        uksi_db_path=uksi_db_path,
        splash=splash
    )
    timing.mark("main window built")

    # Round 6 (11 Oct 2026, Wil: "window early, rest behind"): Home, Observation Data,
    # Contributed and Insect Collection are loaded now, under the splash screen; the window
    # then opens and the Recording Scheme records, Stats/Reports, Mapping, Settings and the
    # species search finish in the background (MainWindow.start_background), the window
    # usable meanwhile. Closing the splash screen stops startup cleanly.
    result = window.preload(timing)
    if result.cancelled:
        timing.mark("startup stopped (splash screen closed)")
        window.deleteLater()
        sys.exit(0)
    splash.finish_progress("Ready")
    timing.mark("first tabs loaded")
    if not result.problems:
        save_seconds(plan.measured, kept_seconds)

    def show():
        finish_and_show(splash, window)
        timing.mark("window shown")
        # the rest, behind the open window ("Still loading: ..." in the status bar);
        # run.bat --timing prints each step "(background)" and "everything ready"
        window.start_background(timing)
        from src.views.startup_preload import problems_message
        message = problems_message(result)
        if message:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(window, "Observatum", message)
    # a moment at 100% so the full bar is seen
    QTimer.singleShot(100, show)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
