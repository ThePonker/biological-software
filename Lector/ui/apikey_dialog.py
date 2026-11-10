"""First-run guide to the free BHL API key (Round 15b).

Shown when no key is found, and from the link at the foot of the left menu. Plain steps,
a button that opens BHL's page for the key, a box to paste it, "Test key" (one cheap BHL
request) and "Save" (writes data\\bhl_api_key.txt, as the README describes)."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLineEdit, QVBoxLayout

from Lector import config
from Lector.service import LectorError
from Lector.ui import style as S

STEPS = ("1. Press “Open the BHL page” below. It opens in your browser.",
         "2. Fill in the short form there. The key is free.",
         "3. BHL sends you the key. It is one line of letters and numbers.",
         "4. Copy the key, paste it into the box below, and press “Test key”.",
         "5. When the test says BHL accepted it, press “Save”.")


class ApiKeyDialog(QDialog):
    def __init__(self, svc, parent=None, first_run=False):
        super().__init__(parent)
        self.svc, self.saved = svc, False
        self.setWindowTitle("BHL API key")
        self.setStyleSheet(S.app_qss())
        self.setMinimumWidth(520)
        v = QVBoxLayout(self)
        v.setSpacing(8)
        v.addWidget(S.label("Lector needs a BHL API key", "h2"))
        v.addWidget(S.label(
            ("There is no key on this computer yet. " if first_run else "")
            + "BHL asks everyone who searches it from a program to use a free key. "
            "It takes a few minutes to get.", "muted", wrap=True))
        for step in STEPS:
            v.addWidget(S.label(step, "body", wrap=True))
        self.open_btn = S.button("Open the BHL page", "view",
                                 f"Opens {config.API_KEY_URL} in your browser", self.open_page)
        row = QHBoxLayout()
        row.addWidget(self.open_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.key_edit = QLineEdit()
        self.key_edit.setObjectName("apiKeyBox")
        self.key_edit.setPlaceholderText("Paste the key here")
        self.key_edit.textChanged.connect(lambda _t: self._buttons())
        v.addWidget(self.key_edit)
        buttons = QHBoxLayout()
        self.test_btn = S.button("Test key", "outline", "Asks BHL one small question to see "
                                 "whether it accepts the key", self.test)
        self.save_btn = S.button("Save", "primary", "Keep the key in " + str(config.KEY_FILE),
                                 self.save)
        self.close_btn = S.button("Close", "cancel", slot=self.reject)
        for b in (self.test_btn, self.save_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        v.addLayout(buttons)
        self.message = S.label("", "small", wrap=True)
        v.addWidget(self.message)
        self._buttons()

    def _buttons(self):
        has = bool(self.key_edit.text().strip())
        self.test_btn.setEnabled(has)
        self.save_btn.setEnabled(has)

    def open_page(self):
        QDesktopServices.openUrl(QUrl(config.API_KEY_URL))

    def test(self):
        """One BHL request. Returns True when BHL accepts the key."""
        self.message.setText("Asking BHL…")
        QApplication.processEvents()
        result = self.svc.test_api_key(self.key_edit.text())
        self.message.setText(result["message"])
        return result["ok"]

    def save(self):
        try:
            path = self.svc.save_api_key(self.key_edit.text())
        except LectorError as exc:
            self.message.setText(str(exc))
            return False
        self.saved = True
        self.message.setText(f"Saved to {path}.")
        self.accept()
        return True
