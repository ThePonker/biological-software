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

from datetime import date

from PySide6.QtCore import QSettings

ORG = "Observatum"          # the one store: Observatum, Data Entry (inside or alone) and the rest
APP = "Observatum V2"
MERGED_KEY = "settings/merged_flauna_observatum"
_OLD_ORG, _OLD_APP = "Flauna", "Observatum"     # Data Entry's old standalone store


def named(organization: str, application: str) -> QSettings:
    """QSettings for organization/application, in the current default format, user scope."""
    return QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope,
                     organization, application)


def app_settings() -> QSettings:
    """The suite's one settings store, whichever program is running."""
    return named(ORG, APP)


def merge_flauna_store_once() -> list:
    """Copy keys from the old Flauna/Observatum store into the Observatum store, only where
    the Observatum store lacks the key (Observatum's value wins). Marks the merge with
    MERGED_KEY (today's date). Never deletes or clears the old store. Idempotent: once the
    mark is set nothing is copied. Returns the keys copied."""
    new = app_settings()
    if new.contains(MERGED_KEY):
        return []
    old = named(_OLD_ORG, _OLD_APP)
    copied = []
    for key in old.allKeys():
        if key == MERGED_KEY or new.contains(key):
            continue
        new.setValue(key, old.value(key))
        copied.append(key)
    new.setValue(MERGED_KEY, date.today().isoformat())
    new.sync()
    return copied


__all__ = ["named", "ORG", "APP", "app_settings", "merge_flauna_store_once"]
