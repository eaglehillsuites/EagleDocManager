"""
Batch Review Dialog - After all forms are generated, shows a checklist
with lease type dropdown and edit button per row.
"""

from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QComboBox, QCheckBox, QFrame,
    QGridLayout, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal


LEASE_TYPES = ["Fixed-Term", "Periodic (Y)", "Periodic (M)"]


class BatchRowWidget(QWidget):
    """One row in the batch checklist."""
    edit_requested = Signal(str)  # emits unit id

    def __init__(self, unit: str, tenant: str, building: str,
                 awaiting_review: bool, previous_lease_type: str | None,
                 parent=None):
        super().__init__(parent)
        self.unit = unit
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Review flag indicator
        self.review_check = QCheckBox()
        self.review_check.setChecked(awaiting_review)
        self.review_check.setToolTip("Awaiting Review")
        layout.addWidget(self.review_check)

        # Unit + tenant info
        info_layout = QVBoxLayout()
        unit_lbl = QLabel(f"<b>{unit}</b>")
        tenant_lbl = QLabel(tenant or "—")
        tenant_lbl.setStyleSheet("color: #555; font-size: 10px;")
        info_layout.addWidget(unit_lbl)
        info_layout.addWidget(tenant_lbl)
        layout.addLayout(info_layout)
        layout.addStretch()

        # Building
        bldg_lbl = QLabel(building or "")
        bldg_lbl.setStyleSheet("color: #666; font-size: 11px;")
        bldg_lbl.setMinimumWidth(120)
        layout.addWidget(bldg_lbl)

        # Edit button
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(60, 28)
        edit_btn.setStyleSheet("""
            QPushButton { background-color: #2c7be5; color: white;
                          border-radius: 3px; font-size: 11px; }
            QPushButton:hover { background-color: #1a68d1; }
        """)
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.unit))
        layout.addWidget(edit_btn)

        # Lease type dropdown
        self.lease_combo = QComboBox()
        self.lease_combo.addItems(LEASE_TYPES)
        self.lease_combo.setFixedWidth(140)
        if previous_lease_type and previous_lease_type in LEASE_TYPES:
            self.lease_combo.setCurrentText(previous_lease_type)
        layout.addWidget(self.lease_combo)

    def get_lease_type(self) -> str:
        return self.lease_combo.currentText()

    def is_awaiting_review(self) -> bool:
        return self.review_check.isChecked()

    def needs_renewal(self) -> bool:
        return self.lease_combo.currentText() == "Fixed-Term"


class BatchReviewDialog(QDialog):
    """
    Shows all generated forms in a checklist.
    User sets lease type per unit and can edit any form.
    Emits which units need renewals when confirmed.
    """

    edit_requested = Signal(str)  # unit id

    def __init__(self, batch_records: list[dict], parent=None):
        """
        batch_records: list of dicts with keys:
            unit, tenant_name, building_addr, awaiting_review,
            previous_lease_type (from last year's tracker, if any)
        """
        super().__init__(parent)
        self.batch_records = batch_records
        self._row_widgets: dict[str, BatchRowWidget] = {}
        self._result: list[dict] | None = None

        self.setWindowTitle("Batch Review — Set Lease Types")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            "<b>Review Generated Forms</b><br>"
            "<span style='color:#555; font-size:11px;'>"
            "Set the lease type for each unit. "
            "Units marked <b>Fixed-Term</b> will have a Renewal form generated. "
            "These selections will be remembered for next year."
            "</span>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Column headers
        col_header = QWidget()
        col_layout = QHBoxLayout(col_header)
        col_layout.setContentsMargins(4, 0, 4, 0)
        col_layout.addWidget(QLabel("Review"), 0)
        col_layout.addWidget(QLabel("Unit / Tenant"), 1)
        col_layout.addStretch()
        col_layout.addWidget(QLabel("Building"), 0)
        col_layout.addWidget(QLabel(""), 0)  # edit btn space
        col_layout.addWidget(QLabel("Lease Type"), 0)
        for lbl in col_header.findChildren(QLabel):
            lbl.setStyleSheet("font-weight: bold; font-size: 11px; color: #555;")
        layout.addWidget(col_header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        # Scroll area for rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        rows_layout = QVBoxLayout(container)
        rows_layout.setSpacing(2)

        for rec in self.batch_records:
            row = BatchRowWidget(
                unit=rec["unit"],
                tenant=rec.get("tenant_name", ""),
                building=rec.get("building_addr", ""),
                awaiting_review=rec.get("awaiting_review", False),
                previous_lease_type=rec.get("previous_lease_type"),
            )
            row.edit_requested.connect(self.edit_requested)

            # Alternating background
            if len(self._row_widgets) % 2 == 1:
                row.setStyleSheet("background-color: #f8f9fa;")

            rows_layout.addWidget(row)
            self._row_widgets[rec["unit"]] = row

        rows_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Legend
        legend = QLabel(
            "☑ Review checkbox = file is flagged 'Awaiting Review' on dashboard"
        )
        legend.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(legend)

        # Buttons
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        layout.addWidget(line2)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.clicked.connect(self.reject)

        fixed_count = sum(
            1 for r in self.batch_records
            if r.get("previous_lease_type") == "Fixed-Term"
        )
        self._confirm_btn = QPushButton("Confirm")
        self._confirm_btn.setFixedHeight(36)
        self._confirm_btn.setStyleSheet("""
            QPushButton { background-color: #2c7be5; color: white;
                          border-radius: 4px; font-weight: bold; padding: 0 16px; }
            QPushButton:hover { background-color: #1a68d1; }
        """)
        self._confirm_btn.clicked.connect(self._on_confirm)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._confirm_btn)
        layout.addLayout(btn_layout)

    def _on_confirm(self):
        self._result = []
        for unit, row_widget in self._row_widgets.items():
            self._result.append({
                "unit": unit,
                "lease_type": row_widget.get_lease_type(),
                "needs_renewal": row_widget.needs_renewal(),
                "awaiting_review": row_widget.is_awaiting_review(),
            })
        self.accept()

    def get_result(self) -> list[dict] | None:
        return self._result

    def update_row_review_state(self, unit: str, awaiting: bool):
        """Called when a form is edited and confirmed/edit-later'd."""
        if unit in self._row_widgets:
            self._row_widgets[unit].review_check.setChecked(awaiting)
