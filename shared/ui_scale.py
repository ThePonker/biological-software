"""ui_scale -- the suite-wide "Interface size" setting (R17, 10 Nov 2026).

Normal (100%), 110%, 125% or 150%. It is stored once, in the suite's settings store
(shared/settings_store.app_settings(), key KEY), and applied to every program by setting
QT_SCALE_FACTOR before its QApplication is made:

    from shared import ui_scale
    ui_scale.apply_before_qapp()        # first, then
    app = QApplication(sys.argv)

A QT_SCALE_FACTOR that is already in the environment is left alone, unless this module set it
(a program started from Atrium inherits Atrium's value; the marker BIOSOFT_SCALE_AUTO says so, and
the stored setting is read again). apply_before_qapp() also sets the high-DPI rounding policy to
PassThrough for every program (Observatum did this alone before).
"""
from __future__ import annotations

import os

KEY = "display/interface_scale_percent"
ENV = "QT_SCALE_FACTOR"
MARK = "BIOSOFT_SCALE_AUTO"
DEFAULT = 100
OPTIONS = ((100, "Normal (100%)", "1"), (110, "110%", "1.1"), (125, "125%", "1.25"),
           (150, "150%", "1.5"))
COMBO_LABEL = "Interface size (all programs; takes effect when a program is next opened):"


def _factor(percent: int) -> str:
    return next((f for p, _l, f in OPTIONS if p == percent), "1")


def load_percent() -> int:
    """The stored size as a percent (100 if unset or not one of the options)."""
    try:
        from shared.settings_store import app_settings
        value = int(app_settings().value(KEY, DEFAULT))
    except Exception:
        return DEFAULT
    return value if any(p == value for p, _l, _f in OPTIONS) else DEFAULT


def save_percent(percent: int) -> None:
    """Store the size for every program (the next time each one starts)."""
    from shared.settings_store import app_settings
    s = app_settings()
    s.setValue(KEY, int(percent) if any(p == percent for p, _l, _f in OPTIONS) else DEFAULT)
    s.sync()


def apply_before_qapp() -> None:
    """Call before QApplication(...): rounding policy PassThrough, and QT_SCALE_FACTOR from the setting."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception as e:                  # never stop a program from starting over this
        print(f"[ui_scale] rounding policy not set: {e}")
    current = os.environ.get(ENV)
    if current is not None and current != os.environ.get(MARK):
        return                              # set by the user (or a test): leave it
    factor = _factor(load_percent())
    os.environ[ENV] = factor
    os.environ[MARK] = factor
