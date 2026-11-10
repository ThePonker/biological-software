"""Sandbox bootstrap for test subprocesses (24 Oct 2026).

conftest.py redirects QSettings to INI files in the worker's temp folder, but a child
interpreter started with `python -c` starts without that, and on Wil's PC would write to the
Windows registry. `child_code(code)` puts the same redirect in front of the child's code:

    subprocess.run([sys.executable, "-c", child_code(code)], ...)

conftest.py exports the folder as BIOSOFT_TEST_QT_DIR (children inherit the environment).
Importable from tests (the tests folder is on sys.path); `bootstrap()` is also what the
prefix runs.
"""
import os

BOOTSTRAP = '''\
import os as _os
_qt = _os.environ.get("BIOSOFT_TEST_QT_DIR")
if not _qt:
    raise SystemExit("sandbox bootstrap: BIOSOFT_TEST_QT_DIR is not set")
from PySide6.QtCore import QSettings as _QS
_QS.setDefaultFormat(_QS.Format.IniFormat)
for _scope in (_QS.Scope.UserScope, _QS.Scope.SystemScope):
    _QS.setPath(_QS.Format.IniFormat, _scope, _qt)
del _os, _qt, _QS, _scope
'''


def child_code(code: str) -> str:
    """`code` with the QSettings sandbox set up first."""
    return BOOTSTRAP + code


def qt_dir() -> str:
    return os.environ["BIOSOFT_TEST_QT_DIR"]
