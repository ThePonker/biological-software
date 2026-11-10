"""R17 C1/C2: gc_schedule (collector driven by a timer) and the QThreadStorage exit filter."""
import gc
import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication

from shared import gc_pause, gc_schedule, qt_messages


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def restore_gc():
    was = gc.isenabled()
    yield
    gc_pause.set_managed(False)
    gc.unfreeze()
    gc.enable() if was else gc.disable()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(clock=None, held=False, visible=False):
    clock = clock or Clock()
    s = gc_schedule.GcScheduler(None, clock=clock, mouse_held=lambda: held,
                                window_visible=lambda: visible)
    return s, clock


def test_tick_levels(qapp, restore_gc):
    s, clock = make()
    assert s.tick() == 0
    clock.t += 10.5
    assert s.tick() == 1
    assert s.tick() == 0
    clock.t += gc_schedule.FULL_EVERY_S
    assert s.tick() == 2
    assert s.runs[2] == 1


def test_full_when_gen2_count_passes(qapp, restore_gc, monkeypatch):
    s, _ = make()
    monkeypatch.setattr(gc, "get_count", lambda: (0, 0, gc_schedule.FULL_AT_GEN2_COUNT))
    assert s.tick() == 2


def test_timer_collects_a_cycle(qapp, restore_gc):
    from PySide6.QtTest import QTest
    gc.disable()
    s, clock = make()
    class Node:
        pass
    def cycle():
        a, b = Node(), Node()
        a.o, b.o = b, a
        return id(a)
    gc.collect()
    ref = []
    import weakref
    a = Node(); a.me = a
    ref.append(weakref.ref(a))
    del a
    assert ref[0]() is not None            # a cycle: reference counting alone does not free it
    s.timer.setInterval(10)
    s.start()
    try:
        QTest.qWait(300)
    finally:
        s.stop()
    assert ref[0]() is None
    assert s.runs[0] >= 1


def test_postponed_while_mouse_button_held(qapp, restore_gc):
    s, _ = make(held=True)
    assert s.tick() == -1 and s.postponed == 1 and s.runs == {0: 0, 1: 0, 2: 0}
    s2 = gc_schedule.GcScheduler(None, mouse_held=lambda: False, window_visible=lambda: False)
    assert s2.tick() >= 0


def test_mouse_buttons_are_asked_of_qt(qapp, monkeypatch):
    from PySide6.QtCore import Qt
    monkeypatch.setattr(QApplication, "mouseButtons", staticmethod(lambda: Qt.MouseButton.LeftButton))
    assert gc_schedule._mouse_held() is True
    monkeypatch.setattr(QApplication, "mouseButtons", staticmethod(lambda: Qt.MouseButton.NoButton))
    assert gc_schedule._mouse_held() is False


def test_postponed_while_a_worker_holds_the_collector(qapp, restore_gc):
    s, _ = make()
    gc_pause.acquire()
    try:
        assert s.tick() == -1
    finally:
        gc_pause.release()
    assert s.tick() >= 0


def test_freeze_once_after_window_shown(qapp, restore_gc):
    s, clock = make(visible=True)
    s.tick()
    assert not s.frozen
    clock.t += gc_schedule.FREEZE_AFTER_S + 1
    s.tick()
    assert s.frozen and gc.get_freeze_count() > 0


def test_env_switch_keeps_automatic_gc(qapp, restore_gc):
    gc.enable()
    assert gc_schedule.auto_requested({"BIOSOFT_GC_AUTO": "1"})
    assert not gc_schedule.auto_requested({})
    assert gc_schedule.install(qapp, env={"BIOSOFT_GC_AUTO": "1"}) is None
    assert gc.isenabled() and not gc_pause.is_managed()


def test_install_disables_auto_and_gc_pause_does_not_reenable(qapp, restore_gc, monkeypatch):
    monkeypatch.setattr(gc_schedule, "_scheduler", None)
    gc.enable()
    sched = gc_schedule.install(qapp, env={})
    try:
        assert sched is not None and not gc.isenabled() and gc_pause.is_managed()
        assert gc_schedule.install(qapp, env={}) is sched          # once only
        gc_pause.acquire()
        gc_pause.release()
        assert not gc.isenabled()                                   # still off after a worker job
    finally:
        sched.stop()


def test_gc_pause_unmanaged_still_reenables(restore_gc):
    gc.enable()
    gc_pause.set_managed(False)
    gc_pause.acquire()
    assert not gc.isenabled()
    gc_pause.release()
    assert gc.isenabled()


def test_memory_stays_bounded_with_cycles_while_timer_runs(qapp, restore_gc):
    from PySide6.QtTest import QTest
    gc.disable()
    gc.collect()
    start = len(gc.get_objects())
    s, _ = make()
    s.timer.setInterval(5)
    s.start()
    class Node:
        pass
    try:
        peak = 0
        for _ in range(40):
            for _ in range(2000):
                a, b = Node(), Node()
                a.o, b.o = b, a
                a.pad = b.pad = bytearray(200)
            QTest.qWait(15)
            peak = max(peak, len(gc.get_objects()))
    finally:
        s.stop()
    gc.collect()
    # 80,000 cycles (about 320,000 tracked objects) were made; with the collector off and no timer
    # they would all still be alive. The timer kept the live count near one batch.
    assert peak - start < 60000, peak - start


def test_thread_storage_noise_is_recognised():
    f = qt_messages.is_thread_storage_exit_noise
    assert f("QThreadStorage: entry 0 destroyed before end of thread 0x1f3a")
    assert f("QThreadStorage: entry 1 destroyed before end of thread 0x7")
    assert not f("QThreadStorage: Thread 0x1 exited after QThreadStorage 3 destroyed")
    assert not f("QFont::setPointSize: Point size <= 0")


SCRIPT = r"""
import sys
from PySide6.QtCore import qWarning, qInstallMessageHandler
if sys.argv[1] == "filter":
    sys.path.insert(0, sys.argv[2])
    from shared import qt_messages
    qt_messages.install()
qWarning("QThreadStorage: entry 0 destroyed before end of thread 0xABC")
qWarning("some other warning stays")
"""


@pytest.mark.parametrize("mode,expect_noise", [("plain", True), ("filter", False)])
def test_filter_drops_only_that_message(tmp_path, mode, expect_noise):
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = tmp_path / "emit.py"
    script.write_text(SCRIPT)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, "-I", str(script), mode, root], capture_output=True,
                       text=True, env=env, timeout=60)
    out = r.stdout + r.stderr
    assert ("destroyed before end of thread" in out) is expect_noise, out
    assert "some other warning stays" in out
