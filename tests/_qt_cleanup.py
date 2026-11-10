"""Shared teardown for tests that build Qt Quick / QtGraphs widgets (25 Oct 2026).

Without a GPU, a QQuickWidget left for the garbage collector can crash a later test's
gc.collect() in the same worker (seen: test_small_fixes teardown after the 3D tests).
Everything a test opened is closed and deleted, and collected, before the next test starts.
"""
import gc

import pytest


@pytest.fixture(autouse=True)
def _delete_new_widgets():
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    before = set(map(id, QApplication.topLevelWidgets())) if app else set()
    yield
    if QApplication.instance() is None:
        return
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.close()
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()
    gc.collect()
