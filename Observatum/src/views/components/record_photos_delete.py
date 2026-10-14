"""Deleting observations that have photos (14 Oct 2026): ask where the photos go first.

ask() is called after Wil has confirmed the delete and before it runs. It returns None when he
cancels (delete nothing), else a function to call once the records are deleted: it removes the
deleted records' photo links and, if he chose, moves the photos into Photos/_Bench (listed in
the cleaning report). Photo files are never deleted (shared/bench_photos.release_records).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QMessageBox

from shared import bench_photos


def _nothing():
    return None


def ask(parent, db_path: str, observation_ids, title: str = "Delete"):
    if not db_path:
        return _nothing
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            by_record = bench_photos.record_photos(conn, observation_ids)
        finally:
            conn.close()
    except Exception as e:
        print(f"[record_photos_delete] photos not checked: {e}")
        return _nothing
    n = len({p for paths in by_record.values() for p in paths})
    if not n:
        return _nothing
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    it = "them" if n != 1 else "it"
    box.setText(f"{n} photo{'s are' if n != 1 else ' is'} linked to "
                f"{'these records' if len(by_record) != 1 else 'this record'}.\n\n"
                f"Photos are never deleted. Move {it} to {bench_photos.BENCH_REL} (listed in the "
                f"cleaning report), or leave {it} in the species folder?")
    to_bench = box.addButton("Move to _Bench", QMessageBox.ButtonRole.AcceptRole)
    leave = box.addButton("Leave in species folder", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(to_bench)
    box.exec()
    if box.clickedButton() not in (to_bench, leave):
        return None
    move = box.clickedButton() is to_bench

    def after():
        try:
            conn = sqlite3.connect(db_path)
            try:
                _moved, notes = bench_photos.release_records(conn, by_record, move)
            finally:
                conn.close()
        except Exception as e:
            notes = [f"photo links not removed: {e}"]
        if notes:
            QMessageBox.warning(parent, title, "\n".join(notes[:20]))
    return after
