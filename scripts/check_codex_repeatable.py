"""Build Codex twice from the same inputs and compare the two results (backlog D7).  SAFE.

    py -3.14 scripts\\check_codex_repeatable.py

Your live codex.db is never written: it is copied (SQLite backup API) into a
temporary folder twice, and build_codex_db.build_codex() is pointed at each copy
in turn -- exactly as a real rebuild would run, manual entries, reviews and
profiles carried over. Each build runs in its own Python process with a
different hash seed, so anything that depends on set or dict ordering shows up.
The clock is pinned so both builds stamp the same time.

Any difference between build A and build B means the build depends on something
other than its inputs (row order, set iteration, a tiebreak), which is the kind
of fault that moved statuses in April. Expected result: "IDENTICAL".

It also lists, for information, how the fresh build differs from your live
codex.db -- e.g. code changes not yet rebuilt (F2's new routings). That part is
not a fault; it tells you what the next real rebuild will change.

Takes a few minutes (it reads the JNCC spreadsheet twice). Exit code 0 = identical.
"""
import contextlib
import io
import os
import subprocess
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime as _real_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths  # noqa: E402
import build_codex_db as bcd  # noqa: E402

PINNED = _real_datetime(2000, 1, 1, 12, 0, 0)
EXAMPLES = 5


class _PinnedClock(_real_datetime):
    @classmethod
    def now(cls, tz=None):
        return PINNED


def _copy_live(dest):
    src = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()


def _build_here(path):
    """Child process: run the real build against `path`."""
    bcd.CODEX_PATH = path
    bcd.datetime = _PinnedClock
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bcd.build_codex()
    sys.stdout.write(out.getvalue())


def _build(path, label, seed):
    """Run the build in a fresh process with its own hash seed. Returns its output."""
    print(f"  Building {label} (hash seed {seed}) ...", flush=True)
    env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--build-into", path],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout + r.stderr


def _tables(conn):
    return {n: s for n, s in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _rows(conn, table):
    return [tuple(r) for r in conn.execute(f"SELECT * FROM [{table}] ORDER BY rowid")]


def compare(path_a, path_b, label_a="A", label_b="B", skip=()):
    """Print the differences; return the number of tables that differ."""
    a = sqlite3.connect(f"file:{path_a}?mode=ro", uri=True)
    b = sqlite3.connect(f"file:{path_b}?mode=ro", uri=True)
    ta, tb = _tables(a), _tables(b)
    differ = 0
    for t in sorted(set(ta) | set(tb)):
        if t in skip:
            continue
        if t not in ta or t not in tb:
            print(f"  {t}: only in {label_a if t in ta else label_b}")
            differ += 1
            continue
        if ta[t] != tb[t]:
            print(f"  {t}: table definition differs")
            differ += 1
            continue
        ra, rb = _rows(a, t), _rows(b, t)
        if ra == rb:
            continue
        differ += 1
        ca, cb = Counter(ra), Counter(rb)
        if ca == cb:
            first = next(i for i, (x, y) in enumerate(zip(ra, rb)) if x != y)
            print(f"  {t}: same {len(ra):,} rows, DIFFERENT ORDER (first at row {first + 1})")
            continue
        only_a, only_b = list((ca - cb).elements()), list((cb - ca).elements())
        print(f"  {t}: {len(ra):,} vs {len(rb):,} rows -- "
              f"{len(only_a):,} only in {label_a}, {len(only_b):,} only in {label_b}")
        for r in only_a[:EXAMPLES]:
            print(f"      {label_a}: {r}")
        for r in only_b[:EXAMPLES]:
            print(f"      {label_b}: {r}")
    a.close()
    b.close()
    return differ


def main():
    if not os.path.exists(paths.CODEX_DB):
        sys.exit(f"codex.db not found: {paths.CODEX_DB}")
    tmp = tempfile.mkdtemp(prefix="codex_repeat_")
    a, b = os.path.join(tmp, "codex_A.db"), os.path.join(tmp, "codex_B.db")
    print("Codex repeatability check -- live codex.db is only read")
    print(f"  Live:  {paths.CODEX_DB}\n  Temp:  {tmp}")
    _copy_live(a)
    _copy_live(b)
    log_a = _build(a, "A", 1)
    log_b = _build(b, "B", 2)
    if "CODEX.DB v5 BUILT" not in log_a or "CODEX.DB v5 BUILT" not in log_b:
        print("\n  A build did not finish. Its output:\n")
        print(log_a if "CODEX.DB v5 BUILT" not in log_a else log_b)
        sys.exit(2)

    print("\n1. Build A vs build B (must be identical)")
    n = compare(a, b)
    print("  IDENTICAL -- the build is repeatable." if n == 0
          else f"\n  {n} table(s) differ -- the build is order-dependent somewhere. Send this to Claude.")

    print("\n2. Live codex.db vs a fresh build (information only)")
    m = compare(str(paths.CODEX_DB), a, "live", "fresh", skip=("metadata", "build_log"))
    if m == 0:
        print("  No difference: the live Codex is what the current code and inputs build.")
    else:
        print(f"\n  {m} table(s) would change at the next real rebuild (see 23_Rebuild_Procedures).")

    print(f"\n  The two temporary builds are left in {tmp} (Windows clears its temp folder;"
          f" nothing here deletes files).")
    sys.exit(0 if n == 0 else 1)


if __name__ == "__main__":
    if "--build-into" in sys.argv:
        _build_here(sys.argv[sys.argv.index("--build-into") + 1])
    else:
        main()
