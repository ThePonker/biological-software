"""Run a read-only job off the GUI thread and hand its result back on it (Home, Round 19).

    run_job(owner, fn, on_done)   fn() runs on a pool thread; on_done(result) runs on the GUI
                                  thread, unless `owner` was asked for a newer job of the same
                                  key meanwhile (the result is then stale and dropped).
Errors are printed and on_done is not called. Jobs open their own database connections.
"""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Done(QObject):
    done = Signal(object, int)


class _Job(QRunnable):
    def __init__(self, fn, token, signals):
        super().__init__()
        self._fn, self._token, self._signals = fn, token, signals

    def run(self):
        try:
            result = self._fn()
        except Exception as e:           # a failed read leaves the card as it was
            print(f"[Home] background read failed: {e}")
            return
        try:
            self._signals.done.emit(result, self._token)
        except RuntimeError:             # the card was closed while this was reading
            pass


class JobRunner(QObject):
    """One per card: start(fn, on_done) supersedes any job still running."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = 0
        self._on_done = None
        self._signals = _Done(self)
        self._signals.done.connect(self._finished)

    def start(self, fn, on_done):
        self._token += 1
        self._on_done = on_done
        QThreadPool.globalInstance().start(_Job(fn, self._token, self._signals))

    def _finished(self, result, token):
        if token == self._token and self._on_done:
            self._on_done(result)

    def busy_token(self) -> int:
        return self._token
