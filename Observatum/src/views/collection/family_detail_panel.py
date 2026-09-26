"""
Taxon Detail Panel - Shows info and editable notes for any taxonomic level.

Displays below the taxonomic tree in the sidebar.
Handles Order, Superfamily, Family, and Species levels.
"""

import sqlite3
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QHBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal

from ...themes import theme
from ...core.config import ButtonColors, TabColors


class FamilyDetailPanel(QWidget):
    """Panel showing taxonomic information and editable notes.

    Despite the class name (kept for compatibility), handles all levels:
    Order, Superfamily, Family, Species.
    """

    # Emitted when user clicks "View Species Profile"
    species_profile_requested = Signal(dict)  # species_data dict

    def __init__(self, family_notes_repo, uksi_db_path: str, parent=None):
        super().__init__(parent)
        self._repo = family_notes_repo
        self._uksi_db_path = uksi_db_path
        self._current_level = ""
        self._current_order = ""
        self._current_name = ""
        self._current_species_data = {}
        self._notes_modified = False
        self._british_species_cache = {}
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        self.name_label = QLabel("")
        self.name_label.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {t.get('text_primary')};")
        layout.addWidget(self.name_label)

        # Subtitle
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet(
            f"font-size: 11px; font-style: italic; color: {t.get('text_secondary')};")
        layout.addWidget(self.subtitle_label)

        # Stats
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            f"font-size: 10px; color: {t.get('text_secondary')};")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        # Extra info
        self.extra_label = QLabel("")
        self.extra_label.setStyleSheet(
            f"font-size: 10px; color: {t.get('text_secondary')};")
        self.extra_label.setWordWrap(True)
        layout.addWidget(self.extra_label)

        # Species profile button
        self.profile_btn = QPushButton("View Species Profile")
        self.profile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TabColors.COLLECTION};
                color: white; border: none; border-radius: 4px;
                padding: 5px 12px; font-size: 10px;
            }}
            QPushButton:hover {{ background-color: #7a7068; }}
        """)
        self.profile_btn.clicked.connect(self._on_profile_clicked)
        self.profile_btn.setVisible(False)
        layout.addWidget(self.profile_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # Notes
        notes_header = QLabel("Notes:")
        notes_header.setStyleSheet(
            f"font-size: 10px; color: {t.get('text_secondary')};")
        layout.addWidget(notes_header)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Add notes...")
        self.notes_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                border: 1px solid {t.get('border')};
                border-radius: 4px; padding: 4px;
                font-size: 10px; background: {t.get('surface')};
            }}
        """)
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        layout.addWidget(self.notes_edit, 1)

        # Save button
        self.save_btn = QPushButton("Save Notes")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white; border: none; border-radius: 4px;
                padding: 4px 12px; font-size: 10px;
            }}
            QPushButton:hover {{ background-color: #3d6649; }}
            QPushButton:disabled {{ background-color: #ccc; color: #888; }}
        """)
        self.save_btn.clicked.connect(self._save_notes)
        layout.addWidget(self.save_btn, 0, Qt.AlignmentFlag.AlignRight)

    @staticmethod
    def _specimens_text(specimen_count, sexes=None):
        """'55' or '55 (\u26425 \u26402 +48)'.

        The bracket appears only where something has been sexed -- 55 unsexed
        specimens are adequately described by 55. Shared with the tree nodes
        and the Data Entry pill via shared/sex_summary.py.
        """
        if not sexes:
            return str(specimen_count)
        try:
            from shared.sex_summary import format_sex_summary
        except ImportError:
            return str(specimen_count)
        s = format_sex_summary(*sexes)
        return f"{specimen_count} ({s})" if s else str(specimen_count)

    def show_order(self, order_name: str, specimen_count: int,
                   species_count: int, families: list, sexes=None):
        """Show order-level detail."""
        self._auto_save()
        self._current_level = "order"
        self._current_order = order_name
        self._current_name = order_name

        self.name_label.setText(order_name)
        self.subtitle_label.setText("Order")

        british = self._count_british("order", order_name)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")

        if families:
            self.extra_label.setText(f"Families: {', '.join(families[:10])}")
            self.extra_label.setVisible(True)
        else:
            self.extra_label.setVisible(False)

        self.profile_btn.setVisible(False)
        self._load_notes(order_name, order_name)

    def show_superfamily(self, order_name: str, superfamily: str,
                         specimen_count: int, species_count: int, families: list,
                         sexes=None):
        """Show superfamily-level detail."""
        self._auto_save()
        self._current_level = "superfamily"
        self._current_order = order_name
        self._current_name = superfamily

        self.name_label.setText(superfamily)
        self.subtitle_label.setText(f"Superfamily — {order_name}")

        british = self._count_british("superfamily", superfamily)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")

        if families:
            self.extra_label.setText(f"Families: {', '.join(families[:10])}")
            self.extra_label.setVisible(True)
        else:
            self.extra_label.setVisible(False)

        self.profile_btn.setVisible(False)
        self._load_notes(order_name, superfamily)

    def show_family(self, order_name: str, family: str,
                    specimen_count: int, species_count: int, genera: list,
                    sexes=None):
        """Show family-level detail."""
        self._auto_save()
        self._current_level = "family"
        self._current_order = order_name
        self._current_name = family

        self.name_label.setText(family)

        notes_data = self._repo.get_notes(order_name, family)
        common_name = notes_data.get('common_name', '') if notes_data else ''
        self.subtitle_label.setText(common_name if common_name else "Family")

        british = self._count_british("family", family)
        self.stats_label.setText(
            f"British species: {british}  |  "
            f"Your specimens: {self._specimens_text(specimen_count, sexes)}"
            f"  |  Your species: {species_count}")

        if genera:
            self.extra_label.setText(f"Genera: {', '.join(genera[:8])}")
            self.extra_label.setVisible(True)
        else:
            self.extra_label.setVisible(False)

        self.profile_btn.setVisible(False)
        self._load_notes(order_name, family)

    def show_species(self, species_name: str, tvk: str, common_name: str,
                     family: str, order_name: str, specimen_count: int,
                     conservation: str, sexes=None):
        """Show species-level detail."""
        self._auto_save()
        self._current_level = "species"
        self._current_order = order_name
        self._current_name = species_name
        self._current_species_data = {
            'species_name': species_name,
            'tvk': tvk,
            'common_name': common_name,
            'family': family,
            'order_name': order_name,
        }

        self.name_label.setText(species_name)
        self.subtitle_label.setText(common_name if common_name else family)

        stats_parts = [f"Specimens: {self._specimens_text(specimen_count, sexes)}"]
        if conservation:
            stats_parts.append(conservation)
        self.stats_label.setText("  |  ".join(stats_parts))

        self.extra_label.setText(f"{family}  —  {order_name}")
        self.extra_label.setVisible(True)

        self.profile_btn.setVisible(True)
        self._load_notes(order_name, species_name)

    def clear(self):
        """Clear the panel."""
        self._auto_save()
        self.name_label.setText("")
        self.subtitle_label.setText("")
        self.stats_label.setText("")
        self.extra_label.setText("")
        self.profile_btn.setVisible(False)
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText("")
        self.notes_edit.blockSignals(False)
        self._notes_modified = False
        self.save_btn.setEnabled(False)

    def _on_notes_changed(self):
        self._notes_modified = True
        self.save_btn.setEnabled(True)

    def _auto_save(self):
        if self._notes_modified and self._current_name:
            self._save_notes()

    def _save_notes(self):
        if not self._current_name:
            return
        common = self.subtitle_label.text() if self._current_level == 'family' else ''
        notes = self.notes_edit.toPlainText()
        self._repo.save_notes(self._current_order, self._current_name, common, notes)
        self._notes_modified = False
        self.save_btn.setEnabled(False)

    def _load_notes(self, order_name: str, name: str):
        notes_data = self._repo.get_notes(order_name, name)
        notes_text = notes_data.get('notes', '') if notes_data else ''
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(notes_text)
        self.notes_edit.blockSignals(False)
        self._notes_modified = False
        self.save_btn.setEnabled(False)

    def _on_profile_clicked(self):
        if self._current_species_data:
            self.species_profile_requested.emit(self._current_species_data)

    def _count_british(self, level: str, name: str) -> int:
        cache_key = f"{level}:{name}"
        if cache_key in self._british_species_cache:
            return self._british_species_cache[cache_key]
        try:
            conn = sqlite3.connect(self._uksi_db_path)
            if level == 'family':
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM taxa WHERE family = ? AND rank = 'Species'",
                    (name,))
            elif level == 'superfamily':
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM taxa WHERE superfamily = ? AND rank = 'Species'",
                    (name,))
            elif level == 'order':
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM taxa WHERE "order" = ? AND rank = \'Species\'',
                    (name,))
            else:
                conn.close()
                return 0
            count = cursor.fetchone()[0]
            conn.close()
            self._british_species_cache[cache_key] = count
            return count
        except Exception:
            return 0
