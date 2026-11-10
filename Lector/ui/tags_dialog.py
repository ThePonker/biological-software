"""Manage tags: add, rename, hide your own reading-list tags (Round 15).

The four standard tags are listed but cannot be changed. A tag some page carries cannot be
deleted, only hidden (hidden tags leave the review pane's buttons; pages that carry them
keep the label)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
                               QVBoxLayout)

from Lector.service import LectorError
from Lector.ui import style as S


def _row_text(t):
    bits = ["standard"] if t["standard"] else []
    if t["hidden"]:
        bits.append("hidden")
    n = t["in_use"]
    bits.append(f"{n:,} page{'s' if n != 1 else ''}" if n else "not used")
    return f"{t['label']}   ({', '.join(bits)})"


class TagsDialog(QDialog):
    def __init__(self, svc, parent=None):
        super().__init__(parent)
        self.svc, self.tags = svc, []
        self.setWindowTitle("Manage tags")
        self.setStyleSheet(S.app_qss())
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setSpacing(8)
        v.addWidget(S.label("Tags say what a page is. The four standard tags stay; add your "
                            "own, rename them, or hide the ones you no longer use. A tag "
                            "that pages carry can only be hidden, not deleted.",
                            "muted", wrap=True))
        self.list = QListWidget()
        self.list.setMinimumHeight(190)
        self.list.currentItemChanged.connect(lambda *_: self._buttons())
        v.addWidget(self.list, 1)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Tag name")
        self.edit.returnPressed.connect(self.add)
        v.addWidget(self.edit)
        row = QHBoxLayout()
        self.add_btn = S.button("Add tag", "primary", "Add the name in the box as a new tag",
                                self.add)
        self.rename_btn = S.button("Rename", "outline", "Give the chosen tag the name in "
                                   "the box", self.rename)
        self.hide_btn = S.button("Hide", "outline", "Hide or show the chosen tag", self.toggle)
        self.delete_btn = S.button("Delete", "delete", "Only a tag no page carries", self.delete)
        for b in (self.add_btn, self.rename_btn, self.hide_btn, self.delete_btn):
            row.addWidget(b)
        row.addStretch(1)
        self.close_btn = S.button("Close", "cancel", slot=self.accept)
        row.addWidget(self.close_btn)
        v.addLayout(row)
        self.message = S.label("", "small", wrap=True)
        v.addWidget(self.message)
        self.reload()

    def reload(self, select=None):
        self.tags = self.svc.list_tags()
        self.list.clear()
        for t in self.tags:
            li = QListWidgetItem(_row_text(t))
            li.setData(Qt.ItemDataRole.UserRole, t["key"])
            if t["hidden"]:
                li.setForeground(self.palette().placeholderText())
            self.list.addItem(li)
            if t["key"] == select:
                self.list.setCurrentItem(li)
        self._buttons()

    def current(self):
        li = self.list.currentItem()
        key = li.data(Qt.ItemDataRole.UserRole) if li else None
        return next((t for t in self.tags if t["key"] == key), None)

    def _buttons(self):
        t = self.current()
        own = t is not None and not t["standard"]
        self.rename_btn.setEnabled(own)
        self.hide_btn.setEnabled(own)
        self.hide_btn.setText("Show" if own and t["hidden"] else "Hide")
        self.delete_btn.setEnabled(own and not t["in_use"])
        self.delete_btn.setToolTip("Only a tag no page carries" if not own or not t["in_use"]
                                   else "This tag is in use: hide it instead")

    def _do(self, fn, *args, select=None, done=""):
        try:
            result = fn(*args)
        except LectorError as exc:
            self.message.setText(str(exc))
            return None
        self.message.setText(done)
        self.reload(select)
        return result

    def add(self):
        key = self._do(self.svc.add_tag, self.edit.text(), done="Tag added.")
        if key:
            self.edit.clear()
            self.reload(key)

    def rename(self):
        t = self.current()
        if t:
            self._do(self.svc.rename_tag, t["key"], self.edit.text(), select=t["key"],
                     done="Tag renamed.")

    def toggle(self):
        t = self.current()
        if t:
            self._do(self.svc.hide_tag, t["key"], not t["hidden"], select=t["key"],
                     done="Tag shown." if t["hidden"] else "Tag hidden.")

    def delete(self):
        t = self.current()
        if t:
            self._do(self.svc.delete_tag, t["key"], done="Tag deleted.")
