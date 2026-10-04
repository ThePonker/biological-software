"""
Species account dialog.

Two layers, never mixed:
  * Published review accounts (codex.db species_profiles) -- read-only, each with
    its citation, newest first, superseded ones last. Shown as reference.
  * Your own account (observatum.db species_profiles, keyed on TVK) -- editable.
    This is the text reports use. Saving and deleting touch only this.

Same constructor and signals as before, so every caller is unchanged:
    SpeciesProfileDialog(species_data: dict, parent)
"""
import html
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QTextBrowser,
    QPushButton, QFrame, QMessageBox, QSplitter, QWidget
)
from PySide6.QtCore import Qt, Signal

from ...models.database import get_database
from ...themes import theme

try:
    from shared.species_accounts import get_species_accounts
except Exception:                      # shared/ unavailable: show no review text
    get_species_accounts = None


class SpeciesProfileDialog(QDialog):
    """Review accounts for reference above; your own account below."""

    profile_saved = Signal(str)  # Emits your account text after save
    profile_deleted = Signal()   # Emits when your account is deleted

    def __init__(self, species_data: Dict, parent=None):
        super().__init__(parent)
        self._species_data = species_data or {}
        self._tvk = (self._species_data.get('tvk') or self._species_data.get('species_tvk') or '').strip() or None
        self._species_name = (self._species_data.get('scientific_name')
                              or self._species_data.get('species_name', '') or '').strip()
        self._original_text = ""
        self._is_new = True

        self.setWindowTitle("Species Account")
        self.setMinimumWidth(820)
        self.setMinimumHeight(640)
        self.setModal(True)

        self._setup_ui()
        self._load_reviews()
        self._load_own()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t.get('surface')}; }}
            QLabel {{ background: transparent; border: none; }}
            QFrame {{ background: transparent; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(4)
        self.name_label = QLabel(self._species_name or 'Unknown Species')
        self.name_label.setStyleSheet(
            f"font-size: {t.font_size('xl')}; font-weight: 600; font-style: italic; "
            f"color: {t.get('text_primary')}; background: transparent; border: none;")
        header.addWidget(self.name_label)
        common_name = self._species_data.get('common_name', '')
        if common_name:
            self.common_label = QLabel(common_name)
            self.common_label.setStyleSheet(
                f"color: {t.get('text_primary')}; font-size: {t.font_size('base')}; "
                "background: transparent; border: none;")
            header.addWidget(self.common_label)
        layout.addLayout(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        layout.addWidget(sep)

        heading = (f"font-weight: 600; color: {t.get('text_heading')}; "
                   f"font-size: {t.font_size('base')}; background: transparent; border: none;")
        box = (f"background-color: {t.get('input_bg')}; border: 1px solid {t.get('border')}; "
               f"border-radius: {t.get('radius_md')}; padding: 10px; color: {t.get('text_primary')}; "
               f"font-size: {t.font_size('base')};")

        # Top pane -- published accounts, read-only
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        self.reviews_label = QLabel("Published accounts  (reference — read-only)")
        self.reviews_label.setStyleSheet(heading)
        tl.addWidget(self.reviews_label)
        self.reviews_view = QTextBrowser()
        self.reviews_view.setOpenExternalLinks(False)
        self.reviews_view.setStyleSheet(f"QTextBrowser {{ {box} }}")
        tl.addWidget(self.reviews_view, 1)

        # Bottom pane -- your account, editable
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        self.own_label = QLabel("Your account  (used in reports)")
        self.own_label.setStyleSheet(heading)
        bl.addWidget(self.own_label)
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText(
            "Write your own account of this species.\n\n"
            "The published text above is for reference. What you write here is "
            "yours, and is what the assessment workbook uses.")
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{ {box} }}
            QTextEdit:focus {{ border: 2px solid {t.get('focus_border')}; }}
        """)
        bl.addWidget(self.text_edit, 1)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(top)
        self.splitter.addWidget(bottom)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([320, 260])
        layout.addWidget(self.splitter, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {t.get('text_primary')}; font-style: italic; background: transparent; border: none;")
        layout.addWidget(self.status_label)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.delete_btn = QPushButton("Delete My Account")
        self.delete_btn.setMinimumHeight(38)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {t.get('error')}; color: white; padding: 8px 20px;
                          border: none; border-radius: {t.get('radius_md')}; font-weight: 500; }}
            QPushButton:hover {{ background-color: {t.get('error_text')}; }}
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setVisible(False)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setMinimumWidth(90)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{ padding: 8px 20px; border: 1px solid {t.get('border_strong')};
                          border-radius: {t.get('radius_md')}; font-weight: 500;
                          background-color: {t.get('surface')}; color: {t.get('text_primary')}; }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save My Account")
        self.save_btn.setMinimumHeight(38)
        self.save_btn.setMinimumWidth(140)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {t.get('success')}; color: white; padding: 8px 24px;
                          border: none; border-radius: {t.get('radius_md')}; font-weight: 600; }}
            QPushButton:hover {{ background-color: {t.get('success_light')}; }}
            QPushButton:disabled {{ background-color: {t.get('border')}; }}
        """)
        self.save_btn.clicked.connect(self._on_save)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

        if not self._tvk:
            self.save_btn.setEnabled(False)
            self.status_label.setText("This record has no TVK, so an account cannot be saved for it.")

    # ------------------------------------------------------------------ load
    def _load_reviews(self):
        """Published accounts through the shared reader: newest first, superseded last."""
        reviews = []
        if get_species_accounts is not None:
            try:
                reviews = get_species_accounts(self._tvk, self._species_name).reviews
            except Exception as e:
                print(f"Error loading review accounts: {e}")
        if not reviews:
            self.reviews_view.setHtml("<p><i>No published review account for this species.</i></p>")
            self.reviews_label.setText("Published accounts  (none)")
            return
        self.reviews_label.setText(f"Published accounts  ({len(reviews)})  — reference, read-only")
        parts = []
        for r in reviews:
            year = (r.date_published or "")[:4]
            cite = r.author or r.cite
            if year and year not in cite:
                cite = f"{cite} {year}"
            head = f"<b>{html.escape(cite)}</b>"
            if r.review_name:
                head += f" — {html.escape(r.review_name)}"
            notes = []
            if r.superseded:
                notes.append("superseded by a later review")
            lic = (r.licence or "").lower()
            if not lic or "internal" in lic or "not openly" in lic:
                notes.append("internal reference — not for reports")
            if notes:
                head += f"<br><i>({'; '.join(notes)})</i>"
            body = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
                           for p in (r.text or "").split("\n\n") if p.strip())
            parts.append(f"<div style='margin-bottom:14px'><p>{head}</p>{body}</div>")
        self.reviews_view.setHtml("<hr>".join(parts))

    def _load_own(self):
        """Your account from observatum.db, by TVK (name only as a fallback for old rows)."""
        if not self._tvk and not self._species_name:
            return
        try:
            db = get_database()
            results = None
            if self._tvk:
                results = db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_tvk = ?", (self._tvk,))
            if (not results or not results[0][0]) and self._species_name:
                results = db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_name = ?", (self._species_name,))
            if results and results[0][0]:
                self._original_text = results[0][0]
                self._is_new = False
                self.text_edit.setPlainText(self._original_text)
                self.delete_btn.setVisible(True)
                self.setWindowTitle("Edit Species Account")
            else:
                self.setWindowTitle("Write Species Account")
        except Exception as e:
            print(f"Error loading your account: {e}")

    # ------------------------------------------------------------------ save / delete
    def _on_save(self):
        """Write your account only -- keyed on TVK, never without one."""
        if not self._tvk:
            QMessageBox.warning(self, "No TVK", "This record has no TVK, so the account cannot be saved.")
            return
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Account",
                                "Please write your account, or click Cancel.\n"
                                "To remove an existing account, use Delete My Account.")
            return
        try:
            db = get_database()
            exists = db.execute_main(
                "SELECT 1 FROM species_profiles WHERE species_tvk = ?", (self._tvk,))
            if exists:
                db.execute_main_write(
                    "UPDATE species_profiles SET profile_text = ?, species_name = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE species_tvk = ?",
                    (text, self._species_name or self._tvk, self._tvk))
            else:
                db.execute_main_write(
                    "INSERT INTO species_profiles (species_tvk, species_name, common_name, profile_text, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (self._tvk, self._species_name or self._tvk,
                     self._species_data.get('common_name', '') or None, text))
            self.profile_saved.emit(text)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save your account:\n\n{e}")

    def _on_delete(self):
        """Delete your account only. Published review text is never touched."""
        if not self._tvk and not self._species_name:
            return
        reply = QMessageBox.question(
            self, "Delete Your Account",
            "Delete your account of this species?\n\n"
            "Published review text is not affected. This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            db = get_database()
            if self._tvk:
                db.execute_main_write("DELETE FROM species_profiles WHERE species_tvk = ?", (self._tvk,))
            else:
                db.execute_main_write("DELETE FROM species_profiles WHERE species_name = ?", (self._species_name,))
            self.profile_deleted.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not delete your account:\n\n{e}")
