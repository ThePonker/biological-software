"""Every app always draws in its light colour scheme (25 Oct 2026).

The suite's styles set light backgrounds but leave some text (record tables, headers) to Qt's
palette. On a Windows PC set to dark mode Qt makes that palette's text white, so the tables
showed white text on white (seen on a friend's PC). Two steps, both harmless on a light PC:

    light_scheme.prepare()        before QApplication(...): Windows is asked not to apply dark mode
    app = QApplication(sys.argv)
    light_scheme.install(app)     after it: the light scheme is pinned (Qt 6.8 and later)

QT_QPA_PLATFORM is only set when nothing has set it already (tests use "offscreen").
"""
from __future__ import annotations

import os
import sys

WINDOWS_LIGHT = "windows:darkmode=0"


def prepare() -> None:
    """Before the QApplication exists: on Windows, the platform plugin's dark mode is off."""
    if sys.platform == "win32" and not os.environ.get("QT_QPA_PLATFORM"):
        os.environ["QT_QPA_PLATFORM"] = WINDOWS_LIGHT


def install(app) -> bool:
    """After the QApplication exists: pin the light colour scheme. True if Qt accepted it."""
    try:
        from PySide6.QtCore import Qt
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        return True
    except Exception as e:                      # an older Qt: prepare() still covers Windows
        print(f"[light_scheme] colour scheme not pinned: {e}")
        return False
