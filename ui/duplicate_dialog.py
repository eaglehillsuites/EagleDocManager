"""
Duplicate Dialog - Side-by-side PDF preview for duplicate resolution.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


def pdf_first_page_pixmap(pdf_path: str, max_width: int = 350) -> QPixmap | None:
    """Convert first page of PDF to QPixmap for preview."""
    if not PDF2IMAGE_AVAILABLE or not Path(pdf_path).exists():
        return None
    try:
        pages = convert_from_path(pdf_path, dpi=100, first_page=1, last_page=1)
        if not pages:
            return None
        img = pages[0]
        img_data = img.tobytes("raw", "RGB")
        qimg = QImage(img_data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width, Qt.SmoothTransformation)
        return pixmap
    except Exception:
        return None


class DuplicateDialog(QDialog):
    """
    Shows side-by-side preview of existing and incoming files.
    Returns "replace", "skip", or "number" via exec().
    """

    def __init__(self, existing_path: str, incoming_path: str,
                 filename: str, parent=None):
        super().__init__(parent)
        self.existing_path = existing_path
        self.incoming_path = incoming_path
        self.filename = filename
        self.result_action = "skip"

        self.setWindowTitle("Duplicate File Detected")
        self.setMinimumWidth(800)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<b>Duplicate detected:</b> {self.filename}")
        header.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(header)

        # Preview area
        preview_layout = QHBoxLayout()

        # Existing file preview
        existing_frame = self._make_preview_panel(
            "Existing File",
            self.existing_path,
            "#ffe0e0"
        )
        preview_layout.addWidget(existing_frame)

        # Incoming file preview
        incoming_frame = self._make_preview_panel(
            "Incoming File",
            self.incoming_path,
            "#e0f0e0"
        )
        preview_layout.addWidget(incoming_frame)

        layout.addLayout(preview_layout)

        # Options
        options_frame = QFrame()
        options_frame.setFrameShape(QFrame.StyledPanel)
        options_frame.setStyleSheet("QFrame { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; }")
        options_layout = QVBoxLayout(options_frame)
        options_layout.setSpacing(6)
        options_layout.addWidget(QLabel("<b>Choose an action:</b>"))

        self.btn_group = QButtonGroup(self)

        radio_style = """
            QRadioButton {
                padding: 8px 10px;
                border-radius: 4px;
                font-size: 13px;
            }
            QRadioButton:checked {
                background-color: #cfe2ff;
                border: 1px solid #2c7be5;
                color: #0a3678;
                font-weight: bold;
            }
            QRadioButton:hover:!checked {
                background-color: #e9ecef;
            }
            QRadioButton::indicator { width: 14px; height: 14px; }
        """

        self.radio_replace = QRadioButton("Replace existing file with incoming file")
        self.radio_skip = QRadioButton("Skip incoming file (leave in source folder)")
        self.radio_number = QRadioButton('Rename both: existing → "(1)", incoming → "(2)"')
        self.radio_skip.setChecked(True)

        for radio in (self.radio_replace, self.radio_skip, self.radio_number):
            radio.setStyleSheet(radio_style)

        self.btn_group.addButton(self.radio_replace, 0)
        self.btn_group.addButton(self.radio_skip, 1)
        self.btn_group.addButton(self.radio_number, 2)

        options_layout.addWidget(self.radio_replace)
        options_layout.addWidget(self.radio_skip)
        options_layout.addWidget(self.radio_number)
        layout.addWidget(options_frame)

        # Confirm button
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setFixedHeight(36)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c7be5;
                color: white;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1a68d1; }
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(confirm_btn)

    def _make_preview_panel(self, title: str, path: str, bg_color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {bg_color}; border-radius: 6px; padding: 4px;")
        layout = QVBoxLayout(frame)

        title_label = QLabel(f"<b>{title}</b>")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        name_label = QLabel(Path(path).name if path else "N/A")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("color: #333; font-size: 11px;")
        layout.addWidget(name_label)

        # Preview image
        pixmap = pdf_first_page_pixmap(path)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        if pixmap:
            img_label.setPixmap(pixmap)
        else:
            img_label.setText("(Preview unavailable)")
            img_label.setStyleSheet("color: #888; font-style: italic;")
        img_label.setMinimumHeight(200)
        layout.addWidget(img_label)

        return frame

    def _on_confirm(self):
        checked_id = self.btn_group.checkedId()
        if checked_id == 0:
            self.result_action = "replace"
        elif checked_id == 1:
            self.result_action = "skip"
        else:
            self.result_action = "number"
        self.accept()

    def get_action(self) -> str:
        return self.result_action
