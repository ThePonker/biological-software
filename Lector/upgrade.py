"""Updating an older lector.db to the current schema (see schema.py).

    dry_run(db_path)            -> report; works on an in-memory copy, changes nothing
    apply(db_path, backup_dir)  -> report; backs up with conn.backup() first, then migrates

Used by `python -m Lector` (asks first), by service.update_database() and by
scripts/migrate_lector_v2.py. The update only adds tables and columns and
fills the new tables; no stored row is changed or removed.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from . import schema


def _ro(db_path):
    return sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)


def status(db_path):
    """{'exists', 'version', 'needs_update'} without changing anything."""
    p = Path(db_path)
    if not p.exists():
        return {"exists": False, "version": None, "needs_update": False}
    conn = _ro(p)
    try:
        return {"exists": True, "version": schema.version(conn),
                "needs_update": schema.needs_migration(conn)}
    finally:
        conn.close()


def dry_run(db_path):
    src = _ro(db_path)
    mem = sqlite3.connect(":memory:")
    try:
        src.backup(mem)
        before = schema.counts(mem)
        made = schema.migrate(mem) if schema.needs_migration(mem) else []
        after = schema.counts(mem)
    finally:
        src.close()
        mem.close()
    return {"before": before, "after": after, "searches_made": made, "backup": None,
            "applied": False}


def backup(db_path, backup_dir):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"lector_pre_v{schema.VERSION}_{datetime.now():%Y%m%d_%H%M%S}.db"
    src = _ro(db_path)
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def apply(db_path, backup_dir):
    if not status(db_path)["needs_update"]:
        report = dry_run(db_path)
        report["applied"] = False
        return report
    dest = backup(db_path, backup_dir)
    conn = sqlite3.connect(str(db_path))
    try:
        before = schema.counts(conn)
        made = schema.migrate(conn)
        after = schema.counts(conn)
    finally:
        conn.close()
    return {"before": before, "after": after, "searches_made": made, "backup": str(dest),
            "applied": True}


def format_report(report):
    lines = [f"{'table':18} {'before':>8} {'after':>8}"]
    for k, a in report["after"].items():
        b = report["before"].get(k)
        lines.append(f"{k:18} {'-' if b is None else b:>8} {'-' if a is None else a:>8}")
    for m in report["searches_made"]:
        lines.append(f"saved search made: {m['name']} ({m['pages']} pages; names: "
                     f"{', '.join(m['names'])})")
    if report.get("backup"):
        lines.append(f"backup: {report['backup']}")
    return "\n".join(lines)
