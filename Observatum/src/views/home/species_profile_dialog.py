"""
Species Profile Dialog.

Popup dialog for creating, editing, and deleting species profiles.
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from ...models.database import get_database
from ...themes import theme


class SpeciesProfileDialog(QDialog):
    """Dialog for managing species profiles."""

    profile_saved = Signal(str)  # Emits profile text after save
    profile_deleted = Signal()   # Emits when profile is deleted

    def __init__(self, species_data: Dict, parent=None):
        super().__init__(parent)
        self._species_data = species_data
        self._tvk = species_data.get('tvk') or species_data.get('species_tvk')
        self._species_name = species_data.get('scientific_name') or species_data.get('species_name', '')
        self._original_text = ""
        self._is_new = True

        self.setWindowTitle("Species Profile")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)

        self._setup_ui()
        self._load_profile()

    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.get('surface')};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QFrame {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with species name
        header = QVBoxLayout()
        header.setSpacing(4)

        display_name = self._species_name or 'Unknown Species'
        self.name_label = QLabel(display_name)
        self.name_label.setStyleSheet(f"""
            font-size: {t.font_size('xl')};
            font-weight: 600;
            font-style: italic;
            color: {t.get('text_primary')};
            background: transparent;
            border: none;
        """)
        header.addWidget(self.name_label)

        common_name = self._species_data.get('common_name', '')
        if common_name:
            self.common_label = QLabel(common_name)
            self.common_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {t.font_size('base')}; background: transparent; border: none;")
            header.addWidget(self.common_label)

        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        layout.addWidget(sep)

        # Profile label
        profile_label = QLabel("Profile Notes")
        profile_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('base')}; background: transparent; border: none;")
        layout.addWidget(profile_label)

        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Add notes about this species...\n\n"
            "For example:\n"
            "• Identification tips\n"
            "• Habitat preferences\n"
            "• Personal observations\n"
            "• Flight period notes\n"
            "• UK distribution info"
        )
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {t.get('input_bg')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                padding: 12px;
                color: {t.get('text_primary')};
                font-size: {t.font_size('base')};
            }}
            QTextEdit:focus {{
                border: 2px solid {t.get('focus_border')};
            }}
        """)
        layout.addWidget(self.text_edit, 1)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # Delete button (left side, only shown if profile exists)
        self.delete_btn = QPushButton("Delete Profile")
        self.delete_btn.setMinimumHeight(38)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('error')};
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {t.get('error_text')}; }}
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setVisible(False)  # Hidden until profile is loaded
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setMinimumWidth(90)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                border: 1px solid {t.get('border_strong')};
                border-radius: {t.get('radius_md')};
                font-weight: 500;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        # Save button
        self.save_btn = QPushButton("Save Profile")
        self.save_btn.setMinimumHeight(38)
        self.save_btn.setMinimumWidth(120)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                padding: 8px 24px;
                border: none;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t.get('success_light')}; }}
        """)
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _load_profile(self):
        """Load existing profile from database."""
        if not self._tvk and not self._species_name:
            return

        try:
            db = get_database()
            results = None
            
            # Try by TVK first
            if self._tvk:
                query = "SELECT profile_text FROM species_profiles WHERE species_tvk = ?"
                results = db.execute_main(query, (self._tvk,))
            
            # Fallback to species_name if no TVK or no result
            if (not results or not results[0][0]) and self._species_name:
                query = "SELECT profile_text FROM species_profiles WHERE species_name = ?"
                results = db.execute_main(query, (self._species_name,))

            if results and results[0][0]:
                self._original_text = results[0][0]
                self._is_new = False
                self.text_edit.setText(self._original_text)
                self.delete_btn.setVisible(True)
                self.setWindowTitle("Edit Species Profile")
            else:
                self.setWindowTitle("Create Species Profile")
        except Exception as e:
            print(f"Error loading profile: {e}")

    def _on_save(self):
        """Save the profile to database."""
        if not self._tvk and not self._species_name:
            QMessageBox.warning(self, "Error", "No species TVK or name available.")
            return

        profile_text = self.text_edit.toPlainText().strip()

        if not profile_text:
            QMessageBox.warning(self, "Empty Profile", "Please enter some profile text or click Cancel.")
            return

        try:
            db = get_database()

            if self._is_new:
                # Insert new profile
                common_name = self._species_data.get('common_name', '')

                query = """
                    INSERT INTO species_profiles (species_tvk, species_name, common_name, profile_text)
                    VALUES (?, ?, ?, ?)
                """
                db.execute_main_write(query, (self._tvk or '', self._species_name, common_name, profile_text))
            else:
                # Update existing profile - use TVK if available, otherwise species_name
                if self._tvk:
                    query = """
                        UPDATE species_profiles
                        SET profile_text = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE species_tvk = ?
                    """
                    db.execute_main_write(query, (profile_text, self._tvk))
                else:
                    query = """
                        UPDATE species_profiles
                        SET profile_text = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE species_name = ?
                    """
                    db.execute_main_write(query, (profile_text, self._species_name))

            self.profile_saved.emit(profile_text)
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save profile:\n\n{str(e)}")

    def _on_delete(self):
        """Delete the profile from database."""
        if not self._tvk and not self._species_name:
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            "Are you sure you want to delete this species profile?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            db = get_database()
            
            # Delete by TVK if available, otherwise by species_name
            if self._tvk:
                query = "DELETE FROM species_profiles WHERE species_tvk = ?"
                db.execute_main_write(query, (self._tvk,))
            else:
                query = "DELETE FROM species_profiles WHERE species_name = ?"
                db.execute_main_write(query, (self._species_name,))

            self.profile_deleted.emit()
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not delete profile:\n\n{str(e)}")
