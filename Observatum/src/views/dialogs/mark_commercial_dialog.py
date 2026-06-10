"""
Mark as Commercial Dialog for Observatum V2.
Allows marking selected observation records as commercial data.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDateEdit, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QDate

from ...themes import theme
from ...models.database import get_database


class MarkCommercialDialog(QDialog):
    """Dialog to mark records as commercial with project/client/embargo details."""

    def __init__(self, record_count: int, parent=None):
        super().__init__(parent)
        self.record_count = record_count
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        self.setWindowTitle("Mark as Commercial")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel(f"Mark {self.record_count} record(s) as Commercial")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t.get('text_primary')};")
        layout.addWidget(header)

        desc = QLabel("Set commercial metadata for the selected records.")
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(desc)

        # Form
        form_group = QGroupBox("Commercial Details")
        form_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
        """)
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)

        input_style = f"""
            QLineEdit, QComboBox, QDateEdit {{
                padding: 6px 10px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border-color: #4a7c59;
            }}
        """

        # Project Name with Browse
        project_row = QHBoxLayout()
        self.project_input = QLineEdit()
        self.project_input.setPlaceholderText("Enter project name...")
        self.project_input.setStyleSheet(input_style)
        project_row.addWidget(self.project_input)
        project_browse = QPushButton("Browse...")
        project_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        project_browse.setFixedWidth(80)
        project_browse.setStyleSheet(f"""
            QPushButton {{
                padding: 6px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
        """)
        project_browse.clicked.connect(lambda: self._browse_values("project_name", self.project_input))
        project_row.addWidget(project_browse)
        form_layout.addRow("Project Name:", project_row)

        # Client with Browse
        client_row = QHBoxLayout()
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("Enter client name...")
        self.client_input.setStyleSheet(input_style)
        client_row.addWidget(self.client_input)
        client_browse = QPushButton("Browse...")
        client_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        client_browse.setFixedWidth(80)
        client_browse.setStyleSheet(f"""
            QPushButton {{
                padding: 6px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
        """)
        client_browse.clicked.connect(lambda: self._browse_values("client", self.client_input))
        client_row.addWidget(client_browse)
        form_layout.addRow("Client:", client_row)

        # Embargo Status
        self.embargo_combo = QComboBox()
        self.embargo_combo.addItems(["None", "Active", "Expired"])
        self.embargo_combo.setStyleSheet(input_style)
        self.embargo_combo.currentTextChanged.connect(self._on_embargo_changed)
        form_layout.addRow("Embargo Status:", self.embargo_combo)

        # Embargo Until
        self.embargo_date = QDateEdit()
        self.embargo_date.setCalendarPopup(True)
        self.embargo_date.calendarWidget().setMinimumWidth(280)
        self.embargo_date.setMinimumWidth(120)
        self.embargo_date.setDate(QDate.currentDate().addYears(1))
        self.embargo_date.setStyleSheet(input_style)
        self.embargo_date.setEnabled(False)
        # Fix calendar popup arrow display (dots -> arrows)
        self.embargo_date.calendarWidget().setStyleSheet("""
            QCalendarWidget QToolButton {
                color: #4a4a4a; font-size: 14px; font-weight: bold; padding: 4px;
            }
            QCalendarWidget QToolButton#qt_calendar_prevmonth { qproperty-text: "<"; }
            QCalendarWidget QToolButton#qt_calendar_nextmonth { qproperty-text: ">"; }
            QCalendarWidget QToolButton::menu-indicator { image: none; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #f5f0eb; }
        """)
        self.embargo_label = QLabel("Embargo Until:")
        form_layout.addRow(self.embargo_label, self.embargo_date)
        self.embargo_date.setVisible(False)
        self.embargo_label.setVisible(False)

        layout.addWidget(form_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid #8b8178;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Mark as Commercial")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setMinimumWidth(150)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #4a7c59;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3d6348; }}
        """)
        apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(apply_btn)

        layout.addLayout(btn_layout)

    def _on_embargo_changed(self, text):
        self.embargo_date.setVisible(text == "Active")
        self.embargo_label.setVisible(text == "Active")

    def _browse_values(self, column: str, target_input: QLineEdit):
        """Browse existing values for a field."""
        t = theme()
        db = get_database()
        try:
            results = db.execute_main_read(
                f"SELECT DISTINCT {column} FROM observations WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
            )
            values = [r[0] for r in results] if results else []
        except Exception:
            values = []

        if not values:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select {column.replace('_', ' ').title()}")
        dialog.setMinimumSize(300, 400)
        layout = QVBoxLayout(dialog)

        lst = QListWidget()
        for v in values:
            lst.addItem(QListWidgetItem(v))
        lst.itemDoubleClicked.connect(lambda item: (target_input.setText(item.text()), dialog.accept()))
        layout.addWidget(lst)

        select_btn = QPushButton("Select")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.clicked.connect(lambda: (
            target_input.setText(lst.currentItem().text()) if lst.currentItem() else None,
            dialog.accept()
        ))
        layout.addWidget(select_btn)
        dialog.exec()

    def get_commercial_data(self) -> dict:
        """Return the commercial metadata."""
        data = {
            "record_type": "Commercial",
            "project_name": self.project_input.text().strip(),
            "client": self.client_input.text().strip(),
        }
        if self.embargo_combo.currentText() == "Active":
            data["embargo_status"] = "Active"
            data["embargo_until"] = self.embargo_date.date().toString("yyyy-MM-dd")
        elif self.embargo_combo.currentText() == "Expired":
            data["embargo_status"] = "Expired"
            data["embargo_until"] = ""
        else:
            data["embargo_status"] = ""
            data["embargo_until"] = ""
        return data
