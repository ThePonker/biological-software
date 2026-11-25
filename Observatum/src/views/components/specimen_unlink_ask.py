"""Deleting observations that specimens are linked to (R4B, 24 Nov 2026).

ask() is called after Wil has confirmed the delete and before it runs. It returns None when
he cancels (delete nothing), False when no specimen is linked, True when he chose to unlink
the specimens (specimens.observation_id set to nothing, in the same transaction as the delete:
shared/observation_delete.delete_observations).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtWidgets import QMessageBox

from shared.observation_delete import describe_links, linked_specimens


def ask(parent, db_path: str, observation_ids, title: str = "Delete") -> Optional[bool]:
    if not db_path:
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            links = linked_specimens(conn, observation_ids)
        finally:
            conn.close()
    except Exception as e:           # the delete itself still refuses linked records
        print(f"[specimen_unlink_ask] links not checked: {e}")
        return False
    if not links:
        return False
    n = len(links)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(f"{n} specimen{'s are' if n != 1 else ' is'} linked to "
                f"{'these records' if len({k['observation_id'] for k in links}) != 1 else 'this record'}:"
                f"\n\n{describe_links(links)}\n\n"
                "Unlink them (they stay in the collection, with no field record) and delete, "
                "or cancel and delete nothing?")
    go = box.addButton("Unlink and delete", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    return True if box.clickedButton() is go else None
