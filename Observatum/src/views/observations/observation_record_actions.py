"""Edit / Delete on an observation's detail dialog opened outside the Observation tab.

The Stats dashboards' "Recent New Species" popup is a RecordDetailDialog: its Edit and
Delete buttons emitted edit_requested / delete_requested and nothing listened (10 Oct
build, "not done" list). They now go to the Observation tab, which owns observation
edits: the same edit dialog (grid ref -> VC and lat/long), and the delete guard's backup
of observatum.db before any delete -- one flow, not a second copy. Where no Observation
tab can be reached, the two buttons are hidden rather than left doing nothing.
"""
from PySide6.QtWidgets import QPushButton


def _hide_edit_delete(dialog) -> None:
    for btn in dialog.findChildren(QPushButton):
        if btn.text() in ("Edit", "Delete"):
            btn.setVisible(False)


def observation_tab_for(widget):
    """The main window's Observation tab, initialised; None when there is none."""
    win = widget.window() if widget is not None else None
    tab = getattr(win, "observation_tab", None)
    if tab is None or not hasattr(tab, "_on_detail_edit_requested"):
        return None
    if hasattr(tab, "initialize"):
        tab.initialize()                     # a no-op once loaded
    return tab


def wire_observation_detail(dialog, source) -> bool:
    """Connect `dialog`'s Edit / Delete to the Observation tab's handlers. Returns False
    (buttons hidden) when the tab can't be reached."""
    tab = observation_tab_for(source)
    if tab is None:
        _hide_edit_delete(dialog)
        return False
    tab._current_detail_dialog = dialog      # its edit handler closes this dialog first
    dialog.edit_requested.connect(tab._on_detail_edit_requested)
    dialog.delete_requested.connect(tab._on_detail_delete_requested)

    def _forget(_result=None):
        if getattr(tab, "_current_detail_dialog", None) is dialog:
            tab._current_detail_dialog = None
    dialog.finished.connect(_forget)
    return True


__all__ = ["wire_observation_detail", "observation_tab_for"]
