"""
Renewal Details Dialog - Shown once after batch review if any Fixed-Term units exist.
Collects shared renewal field values that apply to ALL renewal forms in the batch.
User can go Back to return to batch review.
"""

from __future__ import annotations
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QFormLayout, QCalendarWidget,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, QDate

from form_filler.date_utils import (
    MONTH_NAMES, ordinal_date_str, month_year_str,
    most_recent_past_month_start, lease_end_from_start,
    new_lease_end_from_end, increase_date_from_lease_start,
    parse_date_input, default_due_date, last_day_of_month
)
import calendar as _cal


class RenewalDetailsDialog(QDialog):
    """
    Collects the batch-wide renewal field values.
    Pre-populated from the BatchSettingsDialog values passed in.
    Returns None if user clicks Back (caller should re-show batch review).
    """

    WENT_BACK = -2  # Custom result code for "Back" action

    def __init__(self, batch_settings: dict, fixed_term_units: list[str],
                 parent=None):
        super().__init__(parent)
        self.batch_settings = batch_settings
        self.fixed_term_units = fixed_term_units
        self._result: dict | None = None
        self._went_back = False

        self.setWindowTitle("Renewal Form Details")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        units_str = ", ".join(self.fixed_term_units)
        header = QLabel(
            f"<b>Fixed-Term Renewal Details</b><br>"
            f"<span style='color:#555; font-size:11px;'>"
            f"These values apply to all {len(self.fixed_term_units)} renewal "
            f"form(s): {units_str}</span>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setVerticalSpacing(10)

        # ── Delivery Date ─────────────────────────────────────
        form.addRow(QLabel("<b>Delivery Date</b> (shown on return-by line):"))

        today = date.today()
        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.setMinimumDate(QDate(today.year, today.month, 1))
        self._calendar.setMaximumDate(
            QDate(today.year, today.month,
                  _cal.monthrange(today.year, today.month)[1])
        )
        # Pre-populate from batch settings
        pre_delivery = batch_settings.get("_delivery_date_obj", today)
        self._calendar.setSelectedDate(
            QDate(pre_delivery.year, pre_delivery.month, pre_delivery.day)
        )
        self._calendar.setMaximumHeight(200)
        self._calendar.clicked.connect(self._on_calendar_clicked)
        self._delivery_date = pre_delivery
        form.addRow(self._calendar)

        self._delivery_display = QLineEdit(ordinal_date_str(pre_delivery))
        self._delivery_display.setReadOnly(True)
        self._delivery_display.setStyleSheet("background:#e9ecef; color:#495057;")
        form.addRow("Delivery Date value:", self._delivery_display)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        form.addRow(line2)

        # ── Lease Start ───────────────────────────────────────
        form.addRow(QLabel("<b>Lease Start Month</b>:"))

        self._lease_start_combo = QComboBox()
        self._lease_start_combo.addItems(MONTH_NAMES)
        # Pre-populate from batch settings lease_start string
        pre_start = batch_settings.get("lease_start", "")
        for i, m in enumerate(MONTH_NAMES):
            if pre_start.startswith(m):
                self._lease_start_combo.setCurrentIndex(i)
                break
        self._lease_start_combo.currentIndexChanged.connect(self._on_lease_start_changed)
        form.addRow("Month:", self._lease_start_combo)

        self._lease_start_display = QLineEdit()
        self._lease_start_display.setReadOnly(True)
        self._lease_start_display.setStyleSheet("background:#e9ecef; color:#495057;")
        form.addRow("Lease Start (field value):", self._lease_start_display)

        # ── Lease End (auto, editable) ────────────────────────
        self._lease_end_input = QLineEdit()
        self._lease_end_input.setPlaceholderText("Auto-calculated")
        form.addRow("Lease End (field value):", self._lease_end_input)

        # ── New End of Lease (auto, editable) ────────────────
        self._new_lease_end_input = QLineEdit()
        self._new_lease_end_input.setPlaceholderText("Auto-calculated")
        form.addRow("New End of Lease (field value):", self._new_lease_end_input)

        # ── Increase Date (auto, editable) ───────────────────
        self._increase_date_input = QLineEdit()
        self._increase_date_input.setPlaceholderText("Auto-calculated")
        form.addRow("Increase Date (field value):", self._increase_date_input)

        # ── Due Date (auto, editable) ─────────────────────────
        self._due_date_input = QLineEdit(
            batch_settings.get("due_date", ordinal_date_str(default_due_date()))
        )
        form.addRow("Due Date (field value):", self._due_date_input)

        layout.addLayout(form)

        # Trigger initial calculation
        self._on_lease_start_changed(self._lease_start_combo.currentIndex())

        # ── Buttons ───────────────────────────────────────────
        line3 = QFrame()
        line3.setFrameShape(QFrame.HLine)
        layout.addWidget(line3)

        btn_layout = QHBoxLayout()

        back_btn = QPushButton("← Back")
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self._on_back)

        confirm_btn = QPushButton("Confirm & Save All Forms")
        confirm_btn.setFixedHeight(36)
        confirm_btn.setStyleSheet("""
            QPushButton { background-color: #5cb85c; color: white;
                          border-radius: 4px; font-weight: bold; padding: 0 16px; }
            QPushButton:hover { background-color: #449d44; }
        """)
        confirm_btn.clicked.connect(self._on_confirm)

        btn_layout.addWidget(back_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)

    # ── Handlers ──────────────────────────────────────────────

    def _on_calendar_clicked(self, qdate: QDate):
        self._delivery_date = date(qdate.year(), qdate.month(), qdate.day())
        self._delivery_display.setText(ordinal_date_str(self._delivery_date))

    def _on_lease_start_changed(self, index: int):
        month_num = index + 1
        lease_start = most_recent_past_month_start(month_num)
        self._lease_start_display.setText(ordinal_date_str(lease_start))
        self._current_lease_start = lease_start

        lease_end = lease_end_from_start(lease_start)
        new_lease_end = new_lease_end_from_end(lease_end)
        increase_date = increase_date_from_lease_start(lease_start)

        self._lease_end_input.setText(ordinal_date_str(lease_end))
        self._new_lease_end_input.setText(month_year_str(new_lease_end))
        self._increase_date_input.setText(ordinal_date_str(increase_date))

    def _on_back(self):
        self._went_back = True
        self.reject()

    def went_back(self) -> bool:
        return self._went_back

    def _on_confirm(self):
        lease_start = self._lease_start_display.text().strip()
        lease_end = self._lease_end_input.text().strip()
        new_lease_end = self._new_lease_end_input.text().strip()
        increase_date = self._increase_date_input.text().strip()
        due_date = self._due_date_input.text().strip()
        delivery = ordinal_date_str(self._delivery_date)

        if not all([lease_start, lease_end, new_lease_end, increase_date, due_date]):
            QMessageBox.warning(self, "Missing Fields",
                                "Please ensure all fields are filled before confirming.")
            return

        self._result = {
            "delivery_date": delivery,
            "due_date": due_date,
            "lease_start": lease_start,
            "lease_end": lease_end,
            "new_lease_end": new_lease_end,
            "increase_date": increase_date,
        }
        self.accept()

    def get_result(self) -> dict | None:
        return self._result
