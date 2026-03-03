"""
Out-Inspection Dialog - Prompts for tenant name when out-inspection is processed.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt


class OutInspectionDialog(QDialog):
    """Prompts user to enter tenant name for folder renaming."""

    def __init__(self, unit: str, unit_folder: str, parent=None):
        super().__init__(parent)
        self.unit = unit
        self.unit_folder = unit_folder
        self.tenant_name = ""

        self.setWindowTitle("Out-Inspection Detected")
        self.setModal(True)
        self.setFixedWidth(420)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        icon_label = QLabel("🏠")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel(f"<b>Out-Inspection Filed: Unit {self.unit}</b>")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px;")
        layout.addWidget(title)

        desc = QLabel(
            f"The folder for unit <b>{self.unit}</b> will be moved to the "
            f"Previous Tenants directory.\n\nPlease enter the tenant's name:"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., John Smith")
        self.name_input.setFixedHeight(36)
        self.name_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.name_input)

        preview_label = QLabel("New folder name preview:")
        preview_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(preview_label)

        self.preview = QLabel(f"<i>{self.unit} - (enter name)</i>")
        self.preview.setStyleSheet("color: #333; font-style: italic; padding: 4px 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self.preview)
        self.name_input.textChanged.connect(self._update_preview)

        btn_layout = QHBoxLayout()
        skip_btn = QPushButton("Skip (Don't Move)")
        skip_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Confirm & Move")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("""
            QPushButton:enabled { background-color: #2c7be5; color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)

        btn_layout.addWidget(skip_btn)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

    def _on_text_changed(self, text: str):
        self.confirm_btn.setEnabled(bool(text.strip()))

    def _update_preview(self, text: str):
        if text.strip():
            self.preview.setText(f"<b>{self.unit} - {text.strip()}</b>")
        else:
            self.preview.setText(f"<i>{self.unit} - (enter name)</i>")

    def _on_confirm(self):
        self.tenant_name = self.name_input.text().strip()
        self.accept()

    def get_tenant_name(self) -> str:
        return self.tenant_name
