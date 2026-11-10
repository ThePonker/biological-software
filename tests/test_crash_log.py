"""25 Oct 2026: shared/crash_log.py leaves a record of a crash (an app started from Atrium has no
console). Each check runs in its own interpreter, writing to a temporary folder."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
from tests.test_light_scheme import ENTRIES  # noqa: E402


def _child(tmp_path, body):
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from pathlib import Path\n"
            "from shared import crash_log\n"
            "crash_log.log_dir = lambda: Path(%r)\n"
            "print('LOG', crash_log.install('test'), flush=True)\n" % (str(ROOT), str(tmp_path))) + body
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, cwd=str(ROOT),
                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "QT_QPA_PLATFORM": "offscreen"})
    logs = sorted(tmp_path.glob("crash_test_*.log"))
    return r, (logs[0].read_text(encoding="utf-8") if logs else "")


def test_uncaught_exception_is_written_with_its_traceback(tmp_path):
    r, log = _child(tmp_path, "raise RuntimeError('boom in the map')\n")
    assert r.returncode != 0
    assert re.search(r"crash_test_\d{4}-\d{2}\.log", r.stdout)
    assert "test started" in log and "Uncaught exception" in log and "boom in the map" in log
    assert "boom in the map" in r.stderr          # still on the console too


def test_exception_in_a_thread_is_written(tmp_path):
    _r, log = _child(tmp_path, "import threading\n"
                               "t = threading.Thread(target=lambda: 1 / 0, name='loader')\n"
                               "t.start(); t.join()\n")
    assert "in thread loader" in log and "ZeroDivisionError" in log


@pytest.mark.skipif(sys.platform == "win32" and not hasattr(__import__("faulthandler"), "_sigsegv"),
                    reason="no test crash available")
def test_hard_crash_leaves_the_stack(tmp_path):
    r, log = _child(tmp_path, "import faulthandler\nfaulthandler._sigsegv()\n")
    assert r.returncode != 0
    assert "Fatal Python error" in log
    assert "Current thread" in log or "Thread 0x" in log


def test_appends_and_never_fails(tmp_path):
    _child(tmp_path, "")
    _r, log = _child(tmp_path, "")
    assert log.count("test started") == 2
    blocker = tmp_path / "a_file"
    blocker.write_text("x")                     # the log folder cannot be made inside a file
    r, _log = _child(blocker / "logs", "print('STILL RUNNING')\n")
    assert "LOG None" in r.stdout and "STILL RUNNING" in r.stdout


@pytest.mark.parametrize("entry", ENTRIES)
def test_every_app_installs_it_before_its_qapplication(entry):
    src = (ROOT / entry).read_text(encoding="utf-8")
    pos = [m.start() for m in re.finditer(r"app = QApplication", src)][-1]
    assert src.rfind("crash_log.install(", 0, pos) != -1, f"{entry}: crash_log not installed first"
