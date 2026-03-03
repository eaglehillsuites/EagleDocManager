"""
Date Popup Dialogs - UI for collecting renewal dates and custom date inputs.
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGridLayout, QGroupBox, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt


MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class RenewalDateDialog(QDialog):
    """
    Shows month buttons for selecting a future renewal month/year.
    Returns formatted string like "Jul2026".
    """

    def __init__(self, date_format: str = "mmmYYYY", form_name: str = "", parent=None):
        super().__init__(parent)
        self.date_format = date_format
        self.form_name = form_name
        self.selected_month = None
        self.selected_year = None
        self.result_value = ""

        self.setWindowTitle("Select Renewal Date")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        if self.form_name:
            layout.addWidget(QLabel(f"<b>Select renewal date for: {self.form_name}</b>"))
        else:
            layout.addWidget(QLabel("<b>Select renewal date:</b>"))

        # Year selector
        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        current_year = datetime.now().year
        self.year_spin.setRange(current_year, current_year + 10)
        self.year_spin.setValue(current_year)
        self.year_spin.setFixedWidth(80)
        self.year_spin.valueChanged.connect(self._update_buttons)
        year_layout.addWidget(self.year_spin)
        year_layout.addStretch()
        layout.addLayout(year_layout)

        # Month buttons
        group = QGroupBox("Month")
        grid = QGridLayout(group)

        self.month_buttons = []
        for i, month in enumerate(MONTHS):
            btn = QPushButton(MONTH_SHORT[i])
            btn.setFixedSize(70, 36)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, m=i+1: self._select_month(m))
            grid.addWidget(btn, i // 4, i % 4)
            self.month_buttons.append(btn)

        layout.addWidget(group)

        # Confirm button
        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setFixedHeight(36)
        self.confirm_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #2c7be5;
                color: white;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(self.confirm_btn)

        self._update_buttons()

    def _update_buttons(self):
        """Disable past months if current year is selected."""
        current = datetime.now()
        selected_year = self.year_spin.value()

        for i, btn in enumerate(self.month_buttons):
            month_num = i + 1
            if selected_year == current.year and month_num <= current.month:
                btn.setEnabled(False)
                btn.setChecked(False)
                if self.selected_month == month_num:
                    self.selected_month = None
                    self.confirm_btn.setEnabled(False)
            else:
                btn.setEnabled(True)

    def _select_month(self, month: int):
        self.selected_month = month
        self.selected_year = self.year_spin.value()

        for i, btn in enumerate(self.month_buttons):
            btn.setChecked((i + 1) == month)

        self.confirm_btn.setEnabled(True)

    def _on_confirm(self):
        if self.selected_month and self.selected_year:
            dt = datetime(self.selected_year, self.selected_month, 1)
            fmt = self.date_format

            # Apply format
            result = fmt
            result = result.replace("yyyy", dt.strftime("%Y"))
            result = result.replace("YYYY", dt.strftime("%Y"))
            result = result.replace("mm", dt.strftime("%m"))
            result = result.replace("dd", dt.strftime("%d"))
            result = result.replace("mmm", MONTH_SHORT[dt.month - 1])
            result = result.replace("MMM", MONTH_SHORT[dt.month - 1])

            self.result_value = result
            self.accept()

    def get_value(self) -> str:
        return self.result_value


class CustomDateDialog(QDialog):
    """Simple text input for custom date/text values."""

    def __init__(self, prompt: str = "Enter value:", form_name: str = "", parent=None):
        super().__init__(parent)
        self.form_name = form_name
        self.result_value = ""

        self.setWindowTitle("Enter Custom Value")
        self.setModal(True)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)

        if form_name:
            layout.addWidget(QLabel(f"<b>{form_name}</b>"))

        layout.addWidget(QLabel(prompt))

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type here...")
        self.text_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_input)

        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setFixedHeight(36)
        self.confirm_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #2c7be5; color: white;
                border-radius: 4px; font-weight: bold;
            }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(self.confirm_btn)

    def _on_text_changed(self, text: str):
        self.confirm_btn.setEnabled(bool(text.strip()))

    def _on_confirm(self):
        self.result_value = self.text_input.text().strip()
        self.accept()

    def get_value(self) -> str:
        return self.result_value


class FormTypeDialog(QDialog):
    """
    Shows a preview of the document and asks user to enter/select a form type.
    """

    def __init__(self, preview_image=None, filename: str = "", parent=None):
        super().__init__(parent)
        self.result_form_type = ""

        self.setWindowTitle("Unknown Form Type")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._build_ui(preview_image, filename)

    def _build_ui(self, preview_image, filename):
        import config_manager
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>No form type detected in: {filename}</b>"))
        layout.addWidget(QLabel("Please select or enter the form type:"))

        # Preview
        if preview_image is not None:
            from PySide6.QtGui import QImage, QPixmap
            from PySide6.QtCore import Qt
            try:
                img_data = preview_image.tobytes("raw", "RGB")
                qimg = QImage(img_data, preview_image.width, preview_image.height,
                              preview_image.width * 3, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                if pixmap.width() > 450:
                    pixmap = pixmap.scaledToWidth(450, Qt.SmoothTransformation)
                img_label = QLabel()
                img_label.setPixmap(pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(img_label)
            except Exception:
                pass

        # Existing form types dropdown
        forms = config_manager.load_forms()
        form_names = [f["name"] for f in forms]

        self.combo = QComboBox()
        self.combo.addItem("-- Select existing form type --")
        self.combo.addItems(form_names)
        self.combo.addItem("-- Enter custom form type below --")
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Or type custom form type...")
        self.custom_input.setVisible(False)
        self.custom_input.textChanged.connect(self._check_confirm)
        layout.addWidget(self.custom_input)

        btn_layout = QHBoxLayout()
        skip_btn = QPushButton("Skip This File")
        skip_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("""
            QPushButton:enabled { background-color: #2c7be5; color: white; border-radius: 4px; font-weight: bold; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)

        btn_layout.addWidget(skip_btn)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

    def _on_combo_changed(self, index: int):
        combo_text = self.combo.currentText()
        if combo_text.startswith("--"):
            self.custom_input.setVisible(True)
        else:
            self.custom_input.setVisible(False)
        self._check_confirm()

    def _check_confirm(self):
        combo_text = self.combo.currentText()
        if not combo_text.startswith("--"):
            self.confirm_btn.setEnabled(True)
        elif self.custom_input.text().strip():
            self.confirm_btn.setEnabled(True)
        else:
            self.confirm_btn.setEnabled(False)

    def _on_confirm(self):
        combo_text = self.combo.currentText()
        if not combo_text.startswith("--"):
            self.result_form_type = combo_text
        else:
            self.result_form_type = self.custom_input.text().strip()
        self.accept()

    def get_form_type(self) -> str:
        return self.result_form_type
