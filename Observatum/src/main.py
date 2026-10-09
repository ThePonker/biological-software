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

    # Wait for RS background worker to finish before showing window. The window opens
    # whatever happens: the worker always sets results_ready (error or not), there is a
    # time limit, and any failure preparing a tab is reported, not left on the splash
    # screen (review OBS-02 / SRCH20b, 9 Oct 2026).
    import time
    wait_started = time.monotonic()
    MAX_WAIT_S = 120

    def check_and_show():
        rs_tab = window.recording_scheme_tab
        worker = getattr(rs_tab, '_data_worker', None)
        if (worker and hasattr(worker, 'results_ready') and not worker.results_ready.is_set()
                and time.monotonic() - wait_started < MAX_WAIT_S):
            # Still loading - update splash and check again
            app.processEvents()
            QTimer.singleShot(100, check_and_show)
            return
        # Worker done (or no worker, or out of time) - prepare the tabs while hidden
        splash.set_progress(95, "Preparing interface...")
        app.processEvents()
        problems = []
        if worker is not None and hasattr(worker, 'results_ready') and not worker.results_ready.is_set():
            problems.append(f"Recording Scheme records were still loading after {MAX_WAIT_S} s; "
                            "they will appear when ready.")
        err = rs_tab.worker_error() if hasattr(rs_tab, 'worker_error') else None
        if err:
            rs_tab._load_error = err             # reported here; the tab won't repeat it
            problems.append(f"Recording Scheme records could not be loaded:\n{err}")
        for name, tab, idx in (("Recording Scheme", rs_tab, 2),
                               ("Insect Collection", window.insect_collection_tab, 3)):
            try:
                tab.initialize(main_db_path, uksi_db_path)
                window._initialized_tabs.add(idx)
            except Exception as e:
                import traceback
                traceback.print_exc()
                problems.append(f"{name} could not be prepared:\n{e}")
        splash.set_progress(100, "Ready!")
        app.processEvents()

        def show():
            finish_and_show(splash, window)
            if problems:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(window, "Observatum", "\n\n".join(problems))
        QTimer.singleShot(200, show)

    check_and_show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
