"""settings_store -- a named QSettings store that tests can redirect (24 Oct 2026).

QSettings("Flauna", "Dialogs") always uses the platform's native store (the registry on
Windows) and ignores QSettings.setDefaultFormat, so a test could not keep it away from Wil's
real settings. named("Flauna", "Dialogs") opens the same store in the app (the default
format is NativeFormat unless something changes it), and the test sandbox in
tests/conftest.py switches the default format to IniFormat in a temporary folder.

    from shared.settings_store import named
    s = named("Flauna", "Dialogs")
"""
from __future__ import annotations

from PySide6.QtCore import QSettings


def named(organization: str, application: str) -> QSettings:
    """QSettings for organization/application, in the current default format, user scope."""
    return QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope,
                     organization, application)


__all__ = ["named"]
