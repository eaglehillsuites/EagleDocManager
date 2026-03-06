"""
Date Popup Dialogs

RenewalDateDialog:
- Year selector is now a QComboBox (avoids arrow/text overlap of QSpinBox on Windows)
- Optional form preview shown on the left
- reject() (Skip) always returns so the worker is never left blocked

FormTypeDialog and CustomDateDialog unchanged except Skip also uses reject().
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGridLayout, QGroupBox, QComboBox, QScrollArea,
    QWidget, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _pil_to_pixmap(pil_img, max_width: int = 340):
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


class RenewalDateDialog(QDialog):
    """
    Month/year selector for renewal dates.
    Left panel: optional form preview.  Right panel: year + month buttons.
    Returns formatted string like "Jul2026".
    """

    def __init__(self, date_format: str = "mmmYYYY", form_name: str = "",
                 preview_image=None, parent=None):
        super().__init__(parent)
        self.date_format = date_format
        self.form_name = form_name
        self.preview_image = preview_image
        self.selected_month = None
        self.selected_year = None
        self.result_value = ""

        self.setWindowTitle("Select Renewal Date")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(14)

        # ── Optional form preview on the left ─────────────────
        if self.preview_image is not None:
            px = _pil_to_pixmap(self.preview_image, max_width=460)
            if px:
                frame = QFrame()
                frame.setFrameShape(QFrame.Box)
                frame.setStyleSheet("QFrame { border: 1px solid #ced4da; }")
                fl = QVBoxLayout(frame)
                fl.setContentsMargins(4, 4, 4, 4)

                scroll = QScrollArea()
                scroll.setWidgetResizable(False)
                scroll.setFrameShape(QFrame.NoFrame)
                img_lbl = QLabel()
                img_lbl.setPixmap(px)
                scroll.setWidget(img_lbl)
                scroll.setFixedSize(px.width() + 12, min(px.height() + 12, 660))

                fl.addWidget(scroll)
                outer.addWidget(frame)

        # ── Controls on the right ──────────────────────────────
        right = QWidget()
        right.setMinimumWidth(300)
        layout = QVBoxLayout(right)
        layout.setSpacing(10)

        hdr = self.form_name or "Select renewal date"
        layout.addWidget(QLabel(f"<b>{hdr}</b>"))

        # Year — QComboBox avoids QSpinBox arrow/text overlap on Windows
        yr = QHBoxLayout()
        yr.addWidget(QLabel("Year:"))
        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(88)
        now = datetime.now()
        for y in range(now.year, now.year + 11):
            self.year_combo.addItem(str(y))
        self.year_combo.currentIndexChanged.connect(self._refresh_months)
        yr.addWidget(self.year_combo)
        yr.addStretch()
        layout.addLayout(yr)

        # Month buttons
        grp = QGroupBox("Month")
        grid = QGridLayout(grp)
        grid.setSpacing(5)
        self.month_buttons = []
        for i, _ in enumerate(MONTHS):
            btn = QPushButton(MONTH_SHORT[i])
            btn.setFixedSize(62, 32)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, m=i + 1: self._pick_month(m))
            grid.addWidget(btn, i // 4, i % 4)
            self.month_buttons.append(btn)
        layout.addWidget(grp)

        # Buttons
        row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setFixedHeight(34)
        skip.setToolTip("Skip — processing will continue without a renewal date")
        skip.clicked.connect(self.reject)

        self.ok_btn = QPushButton("Confirm")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setFixedHeight(34)
        self.ok_btn.setStyleSheet("""
            QPushButton:enabled {
                background:#2c7be5; color:white;
                border-radius:4px; font-weight:bold;
            }
            QPushButton:disabled { background:#ced4da; color:#6c757d; }
        """)
        self.ok_btn.clicked.connect(self._confirm)
        row.addWidget(skip)
        row.addStretch()
        row.addWidget(self.ok_btn)
        layout.addLayout(row)

        outer.addWidget(right)
        self._refresh_months()

    def _sel_year(self) -> int:
        return int(self.year_combo.currentText())

    def _refresh_months(self):
        now = datetime.now()
        yr = self._sel_year()
        for i, btn in enumerate(self.month_buttons):
            past = (yr == now.year and i + 1 <= now.month)
            btn.setEnabled(not past)
            if past and btn.isChecked():
                btn.setChecked(False)
                self.selected_month = None
                self.ok_btn.setEnabled(False)

    def _pick_month(self, m: int):
        self.selected_month = m
        self.selected_year = self._sel_year()
        for i, btn in enumerate(self.month_buttons):
            btn.setChecked(i + 1 == m)
        self.ok_btn.setEnabled(True)

    def _confirm(self):
        if self.selected_month and self.selected_year:
            dt = datetime(self.selected_year, self.selected_month, 1)
            r = self.date_format
            # Replace longer tokens first to prevent partial matches
            r = r.replace("mmm", MONTH_SHORT[dt.month - 1])
            r = r.replace("MMM", MONTH_SHORT[dt.month - 1])
            r = r.replace("YYYY", dt.strftime("%Y")).replace("yyyy", dt.strftime("%Y"))
            r = r.replace("mm", dt.strftime("%m")).replace("dd", dt.strftime("%d"))
            self.result_value = r
            self.accept()

    def get_value(self) -> str:
        return self.result_value


class CustomDateDialog(QDialog):
    def __init__(self, prompt: str = "Enter value:", form_name: str = "", parent=None):
        super().__init__(parent)
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
        self.text_input.textChanged.connect(lambda t: self.ok_btn.setEnabled(bool(t.strip())))
        layout.addWidget(self.text_input)

        row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Confirm")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setFixedHeight(36)
        self.ok_btn.setStyleSheet("""
            QPushButton:enabled { background:#2c7be5; color:white; border-radius:4px; font-weight:bold; }
            QPushButton:disabled { background:#ced4da; }
        """)
        self.ok_btn.clicked.connect(self._confirm)
        row.addWidget(skip)
        row.addStretch()
        row.addWidget(self.ok_btn)
        layout.addLayout(row)

    def _confirm(self):
        self.result_value = self.text_input.text().strip()
        self.accept()

    def get_value(self) -> str:
        return self.result_value


class FormTypeDialog(QDialog):
    """
    Shown when a form type cannot be identified automatically.

    When the user confirms:
    - If OCR text is available, the program extracts candidate keywords
      and automatically saves them to the chosen form's ocr_keywords list.
    - This means the same form will be auto-recognised next time.
    """

    def __init__(self, preview_image=None, filename: str = "",
                 ocr_text: str = "", parent=None):
        super().__init__(parent)
        self.result_form_type = ""
        self._ocr_text = ocr_text
        self.setWindowTitle("Unknown Form Type")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._build_ui(preview_image, filename)

    def _build_ui(self, preview_image, filename):
        import config_manager
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>No form type detected in: {filename}</b>"))
        layout.addWidget(QLabel("Please select or enter the form type:"))

        if preview_image is not None:
            px = _pil_to_pixmap(preview_image, max_width=450)
            if px:
                scroll = QScrollArea()
                scroll.setWidgetResizable(False)
                scroll.setFrameShape(QFrame.NoFrame)
                lbl = QLabel()
                lbl.setPixmap(px)
                scroll.setWidget(lbl)
                scroll.setFixedHeight(min(px.height() + 8, 400))
                layout.addWidget(scroll)

        forms = config_manager.load_forms()
        self.combo = QComboBox()
        self.combo.addItem("-- Select existing form type --")
        self.combo.addItems([f["name"] for f in forms])
        self.combo.addItem("-- Enter custom form type below --")
        self.combo.currentIndexChanged.connect(self._combo_changed)
        layout.addWidget(self.combo)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Or type custom form type...")
        self.custom_input.setVisible(False)
        self.custom_input.textChanged.connect(self._check)
        layout.addWidget(self.custom_input)

        # Keyword auto-save notice (only show when OCR text is available)
        if self._ocr_text.strip():
            from processor.ocr_reader import extract_candidate_keywords
            kws = extract_candidate_keywords(self._ocr_text)
            if kws:
                self._auto_keywords = kws
                kw_lbl = QLabel(
                    f"<small><b>Auto-detected keywords:</b> "
                    f"{', '.join(kws)}<br>"
                    "These will be saved to the selected form type so it is "
                    "recognised automatically next time.</small>"
                )
                kw_lbl.setWordWrap(True)
                kw_lbl.setStyleSheet(
                    "background: #e8f4f8; border: 1px solid #bee5eb; "
                    "border-radius: 4px; padding: 6px; color: #0c5460;"
                )
                layout.addWidget(kw_lbl)
            else:
                self._auto_keywords = []
        else:
            self._auto_keywords = []

        row = QHBoxLayout()
        skip = QPushButton("Skip This File")
        skip.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Confirm")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setStyleSheet("""
            QPushButton:enabled { background:#2c7be5; color:white;
                                  border-radius:4px; font-weight:bold; }
            QPushButton:disabled { background:#ced4da; }
        """)
        self.ok_btn.clicked.connect(self._confirm)
        row.addWidget(skip)
        row.addWidget(self.ok_btn)
        layout.addLayout(row)

    def _combo_changed(self):
        self.custom_input.setVisible(self.combo.currentText().startswith("--"))
        self._check()

    def _check(self):
        ok = (not self.combo.currentText().startswith("--") or
              bool(self.custom_input.text().strip()))
        self.ok_btn.setEnabled(ok)

    def _confirm(self):
        if not self.combo.currentText().startswith("--"):
            self.result_form_type = self.combo.currentText()
        else:
            self.result_form_type = self.custom_input.text().strip()

        # Auto-save keywords to chosen form type
        if self._auto_keywords and self.result_form_type:
            try:
                import config_manager
                forms = config_manager.load_forms()
                for i, f in enumerate(forms):
                    if f["name"].lower() == self.result_form_type.lower():
                        existing = f.get("ocr_keywords", [])
                        # Add keywords not already present
                        new_kws = [kw for kw in self._auto_keywords
                                   if kw not in existing and
                                   not any(kw in grp if isinstance(grp, list)
                                           else kw == grp
                                           for grp in existing)]
                        if new_kws:
                            forms[i]["ocr_keywords"] = existing + new_kws
                            config_manager.save_forms(forms)
                        break
            except Exception:
                pass  # Don't let keyword saving crash the dialog

        self.accept()

    def get_form_type(self) -> str:
        return self.result_form_type
