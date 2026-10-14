"""Every dialog remembers its size (14 Oct 2026).

install(app) once, after the QApplication is made: from then on each dialog window (a
QDialog of any kind made by the suite) opens at the size Wil last left it, between sessions.
Kept per dialog type in QSettings("Flauna", "Dialogs"). Message boxes and the system's
file / colour / font pickers are left alone, and a saved size never exceeds the screen.
Size only -- not position -- so a dialog never opens off-screen after a monitor change.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSettings, QSize
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QErrorMessage, QFileDialog, QFontDialog, QInputDialog, QMessageBox,
    QProgressDialog, QWizard,
)

SKIP = (QMessageBox, QFileDialog, QColorDialog, QFontDialog, QInputDialog, QProgressDialog,
        QErrorMessage)
_FLAG = "_bs_size_restored"


def key_for(dialog) -> str:
    t = type(dialog)
    return f"{t.__module__}.{t.__name__}".replace("/", ".")


def _settings() -> QSettings:
    return QSettings("Flauna", "Dialogs")


_WATCHED = (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Close)


class DialogSizes(QObject):
    def eventFilter(self, obj, event):
        try:
            et = event.type()
            if et not in _WATCHED:                  # every other event: straight through
                return False
            # a named dialog only: plain QDialog / QWizard built in place share one class
            # name, so one size would follow them all
            if (isinstance(obj, QDialog) and type(obj) not in (QDialog, QWizard)
                    and not isinstance(obj, SKIP) and obj.isWindow()):
                if et == QEvent.Type.Show and not obj.property(_FLAG):
                    obj.setProperty(_FLAG, True)
                    restore(obj)
                elif et != QEvent.Type.Show and obj.property(_FLAG) and not (
                        obj.isMaximized() or obj.isFullScreen()):
                    save(obj)
        except Exception:                           # never get in the way of a dialog
            pass
        return False


def restore(dialog) -> bool:
    v = _settings().value(key_for(dialog), None)
    try:
        w, h = (int(x) for x in str(v).split("x"))
    except (TypeError, ValueError):
        return False
    screen = dialog.screen()
    if screen is not None:
        avail = screen.availableGeometry()
        w, h = min(w, avail.width()), min(h, avail.height())
    w, h = max(w, dialog.minimumWidth()), max(h, dialog.minimumHeight())
    if w > 0 and h > 0:
        dialog.resize(QSize(w, h))
        return True
    return False


def save(dialog) -> None:
    s = dialog.size()
    if s.width() > 0 and s.height() > 0:
        _settings().setValue(key_for(dialog), f"{s.width()}x{s.height()}")


_installed = []


def install(app) -> None:
    """Remember every dialog's size in this application (idempotent)."""
    if app is None or _installed:
        return
    f = DialogSizes(app)
    app.installEventFilter(f)
    _installed.append(f)


__all__ = ["install", "restore", "save", "key_for", "DialogSizes"]
