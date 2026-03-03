"""
Form Review Dialog - Shown after each form is filled.
Options: Confirm, Edit Now, Edit Later.
If blank fields are detected, goes straight to Edit Now.
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFormLayout, QLineEdit, QFrame,
    QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage

try:
    from pdf2image import convert_from_path
    _PDF2IMAGE = True
except ImportError:
    _PDF2IMAGE = False


INTENTIONALLY_BLANK = {
    "text_13gwqo", "text_14yipe", "text_15rggw", "text_16jpcq"
}


def _pdf_preview_pixmap(pdf_path: str, max_width: int = 380) -> QPixmap | None:
    if not _PDF2IMAGE or not Path(pdf_path).exists():
        return None
    try:
        pages = convert_from_path(pdf_path, dpi=120, first_page=1, last_page=1)
        if not pages:
            return None
        img = pages[0]
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
        px = QPixmap.fromImage(qimg)
        if px.width() > max_width:
            px = px.scaledToWidth(max_width, Qt.SmoothTransformation)
        return px
    except Exception:
        return None


class FormReviewDialog(QDialog):
    """
    Shows a preview of the filled PDF alongside editable fields.

    result_action: "confirm" | "edit_later"
    result_fields: updated field dict if user edited
    """

    # Start in edit mode if blank fields exist
    def __init__(self, pdf_path: str, fields: dict[str, str],
                 form_label: str = "", force_edit: bool = False,
                 parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.fields = dict(fields)
        self.form_label = form_label
        self.result_action = "edit_later"
        self.result_fields = dict(fields)

        self._edit_inputs: dict[str, QLineEdit] = {}
        self._edit_mode = force_edit

        self.setWindowTitle(f"Review — {form_label}" if form_label else "Review Form")
        self.setMinimumSize(820, 600)
        self.setModal(True)
        self._build_ui()

        if force_edit:
            self._enter_edit_mode()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"<b>{self.form_label}</b>" +
            (" — <span style='color:#d9534f'>Blank fields detected — please review</span>"
             if self._edit_mode else "")
        )
        header.setStyleSheet("font-size: 13px; padding: 4px 0;")
        layout.addWidget(header)

        # Main split: preview left, fields right
        splitter = QSplitter(Qt.Horizontal)

        # Left: PDF preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(QLabel("<b>Preview</b>"))

        px = _pdf_preview_pixmap(self.pdf_path)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        if px:
            self._preview_label.setPixmap(px)
        else:
            self._preview_label.setText("(Preview unavailable)")
            self._preview_label.setStyleSheet("color: #888; font-style: italic;")

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(self._preview_label)
        preview_layout.addWidget(preview_scroll)
        splitter.addWidget(preview_widget)

        # Right: field editor
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(8, 0, 0, 0)
        fields_layout.addWidget(QLabel("<b>Form Fields</b>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._form_layout = QFormLayout(container)
        self._form_layout.setLabelAlignment(Qt.AlignRight)

        for field_name, value in self.fields.items():
            if field_name in INTENTIONALLY_BLANK:
                continue
            lbl = QLabel(field_name + ":")
            inp = QLineEdit(str(value))
            inp.setReadOnly(not self._edit_mode)
            if not self._edit_mode:
                inp.setStyleSheet("background: #f0f0f0; color: #495057;")
            self._form_layout.addRow(lbl, inp)
            self._edit_inputs[field_name] = inp

        scroll.setWidget(container)
        fields_layout.addWidget(scroll)
        splitter.addWidget(fields_widget)
        splitter.setSizes([400, 380])
        layout.addWidget(splitter)

        # Action buttons
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #dee2e6;")
        layout.addWidget(line)

        self._btn_layout = QHBoxLayout()
        self._build_action_buttons()
        layout.addLayout(self._btn_layout)

    def _build_action_buttons(self):
        # Clear existing buttons
        while self._btn_layout.count():
            item = self._btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._edit_mode:
            # Edit mode buttons: Edit Later | Confirm
            edit_later_btn = QPushButton("Save & Edit Later")
            edit_later_btn.setFixedHeight(36)
            edit_later_btn.setStyleSheet("""
                QPushButton { background-color: #f0ad4e; color: white;
                              border-radius: 4px; font-weight: bold; padding: 0 12px; }
                QPushButton:hover { background-color: #ec971f; }
            """)
            edit_later_btn.clicked.connect(self._on_edit_later)

            confirm_btn = QPushButton("Confirm")
            confirm_btn.setFixedHeight(36)
            confirm_btn.setStyleSheet("""
                QPushButton { background-color: #5cb85c; color: white;
                              border-radius: 4px; font-weight: bold; padding: 0 12px; }
                QPushButton:hover { background-color: #449d44; }
            """)
            confirm_btn.clicked.connect(self._on_confirm)

            self._btn_layout.addWidget(edit_later_btn)
            self._btn_layout.addStretch()
            self._btn_layout.addWidget(confirm_btn)
        else:
            # Preview mode buttons: Edit Now | Edit Later | Confirm
            edit_now_btn = QPushButton("Edit Now")
            edit_now_btn.setFixedHeight(36)
            edit_now_btn.setStyleSheet("""
                QPushButton { background-color: #2c7be5; color: white;
                              border-radius: 4px; font-weight: bold; padding: 0 12px; }
                QPushButton:hover { background-color: #1a68d1; }
            """)
            edit_now_btn.clicked.connect(self._enter_edit_mode)

            edit_later_btn = QPushButton("Edit Later")
            edit_later_btn.setFixedHeight(36)
            edit_later_btn.setStyleSheet("""
                QPushButton { background-color: #f0ad4e; color: white;
                              border-radius: 4px; font-weight: bold; padding: 0 12px; }
                QPushButton:hover { background-color: #ec971f; }
            """)
            edit_later_btn.clicked.connect(self._on_edit_later)

            confirm_btn = QPushButton("Confirm")
            confirm_btn.setFixedHeight(36)
            confirm_btn.setStyleSheet("""
                QPushButton { background-color: #5cb85c; color: white;
                              border-radius: 4px; font-weight: bold; padding: 0 12px; }
                QPushButton:hover { background-color: #449d44; }
            """)
            confirm_btn.clicked.connect(self._on_confirm)

            self._btn_layout.addWidget(edit_now_btn)
            self._btn_layout.addWidget(edit_later_btn)
            self._btn_layout.addStretch()
            self._btn_layout.addWidget(confirm_btn)

    def _enter_edit_mode(self):
        self._edit_mode = True
        for inp in self._edit_inputs.values():
            inp.setReadOnly(False)
            inp.setStyleSheet("")
        self._build_action_buttons()

    def _collect_fields(self) -> dict[str, str]:
        result = dict(self.fields)
        for field_name, inp in self._edit_inputs.items():
            result[field_name] = inp.text()
        return result

    def _on_confirm(self):
        self.result_action = "confirm"
        self.result_fields = self._collect_fields()
        self.accept()

    def _on_edit_later(self):
        self.result_action = "edit_later"
        self.result_fields = self._collect_fields()
        self.accept()
