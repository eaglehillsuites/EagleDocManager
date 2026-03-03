"""
Part Editor Dialog - Popup for adding/editing naming convention parts.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QStackedWidget, QWidget, QFormLayout
)
from PySide6.QtCore import Qt


PART_TYPES = ["Plain Text", "Unit #", "Today's Date", "Form Name", "Date (Renewal)", "Date (Custom)"]


class PartEditorDialog(QDialog):
    """Dialog for creating or editing a single naming convention part."""

    def __init__(self, existing_part: dict = None, parent=None):
        super().__init__(parent)
        self.result_part = None
        self.existing = existing_part or {}

        self.setWindowTitle("Edit Naming Part")
        self.setModal(True)
        self.setFixedWidth(380)

        self._build_ui()

        if self.existing:
            self._populate_from_existing()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Part Type:</b>"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(PART_TYPES)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        # Stacked widget for type-specific options
        self.stack = QStackedWidget()

        # 0: Plain Text
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.addWidget(QLabel("Text to insert:"))
        self.plain_text_input = QLineEdit()
        self.plain_text_input.setPlaceholderText('e.g., " - " or " Increase "')
        self.plain_text_input.textChanged.connect(self._check_confirm)
        text_layout.addWidget(self.plain_text_input)
        self.stack.addWidget(text_widget)

        # 1: Unit # (no extra input needed)
        unit_widget = QWidget()
        unit_layout = QVBoxLayout(unit_widget)
        unit_layout.addWidget(QLabel("Unit number will be inserted automatically\nfrom the QR code on the document."))
        self.stack.addWidget(unit_widget)

        # 2: Today's Date (no extra input)
        today_widget = QWidget()
        today_layout = QVBoxLayout(today_widget)
        today_layout.addWidget(QLabel("Today's date will be inserted automatically\nusing the naming convention's date format."))
        self.stack.addWidget(today_widget)

        # 3: Form Name (no extra input)
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.addWidget(QLabel("The form type name will be inserted automatically."))
        self.stack.addWidget(form_widget)

        # 4: Date (Renewal) - no extra input, popup appears at processing time
        renewal_widget = QWidget()
        renewal_layout = QVBoxLayout(renewal_widget)
        renewal_layout.addWidget(QLabel(
            "A renewal date popup will appear when processing\n"
            "documents with this naming convention.\n\n"
            "User selects a future month/year."
        ))
        self.stack.addWidget(renewal_widget)

        # 5: Date (Custom) - no extra input
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        custom_layout.addWidget(QLabel(
            "A custom text box will appear when processing\n"
            "documents with this naming convention."
        ))
        self.stack.addWidget(custom_widget)

        layout.addWidget(self.stack)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self.add_btn = QPushButton("Add Part")
        self.add_btn.setStyleSheet("""
            QPushButton:enabled { background-color: #2c7be5; color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.add_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)

        self._on_type_changed(0)

    def _on_type_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        self._check_confirm()
        if self.existing:
            self.add_btn.setText("Save Part")
        else:
            self.add_btn.setText("Add Part")

    def _check_confirm(self):
        idx = self.type_combo.currentIndex()
        if idx == 0:  # Plain text requires text
            self.add_btn.setEnabled(bool(self.plain_text_input.text()))
        else:
            self.add_btn.setEnabled(True)

    def _populate_from_existing(self):
        part_type = self.existing.get("type", "text")
        type_map = {
            "text": 0,
            "unit": 1,
            "date_today": 2,
            "form_name": 3,
            "date_renewal": 4,
            "date_custom": 5,
        }
        idx = type_map.get(part_type, 0)
        self.type_combo.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)
        if part_type == "text":
            self.plain_text_input.setText(self.existing.get("value", ""))
        self.add_btn.setText("Save Part")

    def _on_confirm(self):
        idx = self.type_combo.currentIndex()
        type_map = ["text", "unit", "date", "form_name", "date", "date"]
        source_map = [None, None, "today", None, "renewal", "custom"]

        part = {"type": type_map[idx]}
        if source_map[idx]:
            part["source"] = source_map[idx]
        if idx == 0:
            part["value"] = self.plain_text_input.text()

        self.result_part = part
        self.accept()

    def get_part(self) -> dict | None:
        return self.result_part


def part_to_display(part: dict) -> str:
    """Convert a part dict to a human-readable string for listboxes."""
    t = part.get("type", "")
    if t == "text":
        return f'Plain Text: "{part.get("value", "")}"'
    elif t == "unit":
        return "Unit #"
    elif t == "form_name":
        return "Form Name"
    elif t == "date":
        source = part.get("source", "today")
        labels = {"today": "Today's Date", "renewal": "Date (Renewal)", "custom": "Date (Custom)"}
        return labels.get(source, f"Date ({source})")
    return str(part)
