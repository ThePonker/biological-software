"""17 Nov 2026: Observatum crashed on opening (Windows 0xc0000374, heap corruption) with the Stats
worker thread at `from PySide6.QtCharts import ...`. The Qt add-on modules are now loaded on the
GUI thread before any background step imports a tab in a worker."""
import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _first_yield_thread(step_name):
    """Run a step to its first yield and record which thread imported the add-ons."""
    import importlib
    import src.views.background_steps as bs
    seen = []
    real = importlib.import_module

    def spy(name, package=None):
        if name in bs.QT_ADDON_MODULES:
            seen.append((name, threading.current_thread() is threading.main_thread()))
        return real(name, package)

    bs.importlib.import_module = spy
    try:
        gen = getattr(bs, step_name)(object())
        first = next(gen)
    finally:
        bs.importlib.import_module = real
    return seen, first


def test_addons_load_on_the_gui_thread_before_the_worker_import():
    from src.views.background_loader import InThread
    for step in ("stats_step", "settings_step", "mapping_step"):
        seen, first = _first_yield_thread(step)
        assert isinstance(first, InThread), step                  # the worker comes after
        names = [n for n, _ in seen]
        assert "PySide6.QtCharts" in names, step
        assert all(on_main for _, on_main in seen), step
