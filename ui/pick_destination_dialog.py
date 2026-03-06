"""
PickDestinationDialog - Shown when a scanned document cannot be automatically
routed because no QR code was found or it couldn't be decoded.

Shows:
  - Clear explanation of WHY the QR failed
  - Preview of the document
  - Folder picker for the destination
  - Editable filename suggestion
  - Option to remember the folder (saves as a QR route if a pattern is identifiable,
    or as a general folder override)
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QScrollArea, QFrame, QCheckBox,
    QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont


def _pil_to_pixmap(pil_img, max_width: int = 380) -> QPixmap | None:
    try:
        rgb = pil_img.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, rgb.width, rgb.height,
                      rgb.width * 3, QImage.Format_RGB888)
        px = QPixmap.fromImage(qimg)
        if px.width() > max_width:
            px = px.scaledToWidth(max_width, Qt.SmoothTransformation)
        return px
    except Exception:
        return None


class PickDestinationDialog(QDialog):
    """
    Ask the user to choose a destination folder for a document that could
    not be automatically routed.

    Args:
        filename:         Original PDF filename
        reason:           Human-readable explanation of why routing failed
        preview_image:    PIL Image of the first page (optional)
        proposed_filename: Suggested output filename (user can edit)
    """

    def __init__(self, filename: str = "", reason: str = "",
                 preview_image=None, proposed_filename: str = "",
                 parent=None):
        super().__init__(parent)
        self.filename = filename
        self.reason = reason
        self.preview_image = preview_image
        self.proposed_filename = proposed_filename or filename
        self._result: dict | None = None

        self.setWindowTitle("Choose Destination")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(14)

        # ── Left: document preview ──────────────────────────────
        if self.preview_image is not None:
            px = _pil_to_pixmap(self.preview_image, max_width=340)
            if px:
                frame = QFrame()
                frame.setFrameShape(QFrame.Box)
                frame.setStyleSheet("QFrame { border: 1px solid #ced4da; }")
                fl = QVBoxLayout(frame)
                fl.setContentsMargins(4, 4, 4, 4)
                scroll = QScrollArea()
                scroll.setWidgetResizable(False)
                scroll.setFrameShape(QFrame.NoFrame)
                lbl = QLabel()
                lbl.setPixmap(px)
                scroll.setWidget(lbl)
                scroll.setFixedSize(px.width() + 12, min(px.height() + 12, 560))
                fl.addWidget(scroll)
                outer.addWidget(frame)

        # ── Right: controls ─────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(10)

        # File info
        file_lbl = QLabel(f"<b>File:</b> {self.filename}")
        file_lbl.setWordWrap(True)
        right.addWidget(file_lbl)

        # Reason box
        reason_frame = QFrame()
        reason_frame.setFrameShape(QFrame.Box)
        reason_frame.setStyleSheet("""
            QFrame { background: #fff3cd; border: 1px solid #ffc107;
                     border-radius: 4px; padding: 2px; }
        """)
        reason_layout = QVBoxLayout(reason_frame)
        reason_layout.setContentsMargins(8, 6, 8, 6)

        warn_lbl = QLabel("⚠  Could not automatically route this file")
        warn_font = QFont()
        warn_font.setBold(True)
        warn_lbl.setFont(warn_font)
        reason_layout.addWidget(warn_lbl)

        detail_lbl = QLabel(self.reason)
        detail_lbl.setWordWrap(True)
        detail_lbl.setStyleSheet("color: #555; font-size: 11px;")
        reason_layout.addWidget(detail_lbl)
        right.addWidget(reason_frame)

        # Filename field
        right.addWidget(QLabel("<b>Output filename:</b>"))
        self.filename_input = QLineEdit(self.proposed_filename)
        self.filename_input.setPlaceholderText("filename.pdf")
        right.addWidget(self.filename_input)

        # Destination folder
        right.addWidget(QLabel("<b>Destination folder:</b>"))
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select a folder…")
        self.folder_input.textChanged.connect(self._check_ok)
        folder_row.addWidget(self.folder_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedHeight(30)
        browse_btn.clicked.connect(self._browse)
        folder_row.addWidget(browse_btn)
        right.addLayout(folder_row)

        # Remember checkbox
        self.remember_check = QCheckBox(
            "Remember this folder for future documents with the same form type"
        )
        right.addWidget(self.remember_check)

        right.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        skip_btn = QPushButton("Skip This File")
        skip_btn.setFixedHeight(34)
        skip_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("Move File Here")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setFixedHeight(34)
        self.ok_btn.setStyleSheet("""
            QPushButton:enabled {
                background: #2c7be5; color: white;
                border-radius: 4px; font-weight: bold; padding: 0 14px;
            }
            QPushButton:hover:enabled { background: #1a68d1; }
            QPushButton:disabled { background: #ced4da; color: #6c757d; }
        """)
        self.ok_btn.clicked.connect(self._confirm)
        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.ok_btn)
        right.addLayout(btn_row)

        outer.addLayout(right)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.folder_input.setText(folder)

    def _check_ok(self):
        self.ok_btn.setEnabled(bool(self.folder_input.text().strip()))

    def _confirm(self):
        folder = self.folder_input.text().strip()
        fname = self.filename_input.text().strip() or self.proposed_filename
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        self._result = {
            "folder": folder,
            "filename": fname,
            "remember": self.remember_check.isChecked(),
        }
        self.accept()

    def get_result(self) -> dict | None:
        """Returns {'folder': str, 'filename': str, 'remember': bool} or None."""
        return self._result
