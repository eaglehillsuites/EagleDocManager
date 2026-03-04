"""
UnknownQRDialog - Shown when a QR code is scanned but not recognised.

Options:
  A) Connect to an existing form type (copies that form's DM value / routing)
  B) Create a new custom route (QR → folder path, persisted in config)
  C) Skip this file
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QRadioButton, QButtonGroup, QFileDialog,
    QGroupBox, QFrame
)
from PySide6.QtCore import Qt
import config_manager


class UnknownQRDialog(QDialog):
    def __init__(self, qr_text: str, filename: str = "", parent=None):
        super().__init__(parent)
        self.qr_text = qr_text
        self.filename = filename
        self._result: dict | None = None

        self.setWindowTitle("Unrecognised QR Code")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        layout.addWidget(QLabel(f"<b>Unrecognised QR code found in:</b> {self.filename}"))
        code_lbl = QLabel(f"QR content:  <code>{self.qr_text}</code>")
        code_lbl.setStyleSheet("background:#f8f9fa; padding:6px; border:1px solid #dee2e6; border-radius:4px;")
        layout.addWidget(code_lbl)

        layout.addWidget(QLabel("How would you like to handle this QR code?"))

        # ── Option A: connect to existing form ─────────────────
        self.radio_form = QRadioButton("Connect to an existing form type")
        self.radio_form.setChecked(True)

        form_box = QGroupBox()
        form_box.setFlat(True)
        fb_layout = QHBoxLayout(form_box)
        fb_layout.setContentsMargins(20, 4, 0, 4)

        forms = config_manager.load_forms()
        self.form_combo = QComboBox()
        for f in forms:
            self.form_combo.addItem(f["name"], f)
        fb_layout.addWidget(QLabel("Form type:"))
        fb_layout.addWidget(self.form_combo)
        fb_layout.addStretch()

        # ── Option B: new custom route ──────────────────────────
        self.radio_route = QRadioButton("Create a new destination route for this QR code")

        route_box = QGroupBox()
        route_box.setFlat(True)
        rb_layout = QHBoxLayout(route_box)
        rb_layout.setContentsMargins(20, 4, 0, 4)

        self.route_input = QLineEdit()
        self.route_input.setPlaceholderText("Destination folder path…")
        self.route_input.setEnabled(False)
        browse_btn = QPushButton("Browse…")
        browse_btn.setEnabled(False)
        browse_btn.setFixedHeight(28)
        browse_btn.clicked.connect(self._browse_route)
        rb_layout.addWidget(self.route_input)
        rb_layout.addWidget(browse_btn)
        self._browse_btn = browse_btn

        # Group radios
        grp = QButtonGroup(self)
        grp.addButton(self.radio_form)
        grp.addButton(self.radio_route)
        grp.buttonToggled.connect(self._on_radio)

        layout.addWidget(self.radio_form)
        layout.addWidget(form_box)
        layout.addWidget(self.radio_route)
        layout.addWidget(route_box)

        # ── Divider ────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#dee2e6;")
        layout.addWidget(line)

        # ── Buttons ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        skip_btn = QPushButton("Skip This File")
        skip_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("Confirm")
        self.ok_btn.setEnabled(True)
        self.ok_btn.setFixedHeight(34)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background:#2c7be5; color:white;
                border-radius:4px; font-weight:bold; padding:0 14px;
            }
            QPushButton:hover { background:#1a68d1; }
        """)
        self.ok_btn.clicked.connect(self._confirm)

        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

        self._route_input = route_box
        self._form_box = form_box
        self._route_line = self.route_input

    def _on_radio(self, btn, checked):
        if not checked:
            return
        is_route = self.radio_route.isChecked()
        self._route_line.setEnabled(is_route)
        self._browse_btn.setEnabled(is_route)
        self.form_combo.setEnabled(not is_route)

    def _browse_route(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self._route_line.setText(folder)

    def _confirm(self):
        if self.radio_form.isChecked():
            form_data = self.form_combo.currentData()
            self._result = {
                "action": "form",
                "form": form_data,
                "form_name": self.form_combo.currentText(),
            }
        else:
            folder = self._route_line.text().strip()
            if not folder:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "No Folder", "Please select a destination folder.")
                return
            self._result = {
                "action": "route",
                "folder": folder,
            }
        self.accept()

    def get_result(self) -> dict | None:
        return self._result
