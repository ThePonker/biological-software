"""Long work off the GUI thread: BHL counts, previews, runs, exports (Lector UI).

One task at a time (the service's BHL client is shared and throttled). A task is a
function called in a QThread with progress= and cancel= keywords, as every NETWORK
method of LectorService takes; its result (or error) comes back as a signal on the
GUI thread. Cancel sets a threading.Event the service checks before every request.

    runner = TaskRunner(parent)
    runner.start("Running Lamia textor", svc.run_search, sid,
                 on_done=show_result, on_error=show_message)
    runner.cancel()            # Cancel button; the run stops within a second
"""
import threading
import traceback

from PySide6.QtCore import QObject, QThread, Signal

from Lector.service import LectorError


class _Worker(QThread):
    progressed = Signal(str, int, int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, args, kwargs, cancel, parent=None):
        super().__init__(parent)
        self._fn, self._args, self._kwargs, self._cancel = fn, args, kwargs, cancel

    def _progress(self, stage, done, total, message):
        # called on the worker thread: only emit (Qt queues it to the GUI thread)
        self.progressed.emit(str(stage), int(done or 0), int(total or 0), str(message or ""))

    def run(self):
        try:
            result = self._fn(*self._args, progress=self._progress, cancel=self._cancel,
                              **self._kwargs)
        except LectorError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - shown to the user, never swallowed
            traceback.print_exc()
            self.failed.emit(f"Something went wrong: {exc}")
        else:
            self.succeeded.emit(result)


class TaskRunner(QObject):
    """Runs one background task at a time and reports on it."""
    started = Signal(str)                    # label
    progressed = Signal(str, int, int, str)  # stage, done, total, message
    finished = Signal()                      # after on_done / on_error ran

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._cancel = None
        self._callbacks = (None, None)
        self.label = ""

    @property
    def busy(self):
        return self._worker is not None

    def start(self, label, fn, *args, on_done=None, on_error=None, **kwargs):
        """Run fn(*args, progress=..., cancel=..., **kwargs) in a thread. False if busy."""
        if self.busy:
            return False
        self.label = label
        self._cancel = threading.Event()
        w = _Worker(fn, args, kwargs, self._cancel, self)
        self._callbacks = (on_done, on_error)
        # bound methods of this QObject: queued to the GUI thread (a bare lambda would
        # run on the worker thread)
        w.progressed.connect(self._on_progress)
        w.succeeded.connect(self._on_success)
        w.failed.connect(self._on_failure)
        self._worker = w
        self.started.emit(label)
        w.start()
        return True

    def _on_progress(self, stage, done, total, message):
        self.progressed.emit(stage, done, total, message)

    def _on_success(self, result):
        self._end(self._callbacks[0], result)

    def _on_failure(self, message):
        self._end(self._callbacks[1], message)

    def _end(self, callback, value):
        w, self._worker = self._worker, None
        if w is not None:
            w.wait()
            w.deleteLater()
        try:
            if callback:
                callback(value)
        finally:
            self.finished.emit()

    def cancel(self):
        if self._cancel is not None:
            self._cancel.set()

    @property
    def cancelling(self):
        return self._cancel is not None and self._cancel.is_set() and self.busy

    def wait(self, ms=None):
        """Block until the worker thread ends (closing the window)."""
        w = self._worker
        if w is None:
            return True
        return w.wait() if ms is None else w.wait(ms)
