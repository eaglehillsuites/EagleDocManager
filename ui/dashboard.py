"""
Dashboard - Main landing window for Eagle Doc Manager.
Shows monthly metrics and provides access to Document Scanner and Form Filler.
"""

from __future__ import annotations
from datetime import date
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QComboBox, QScrollArea, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor

from form_filler import tracker
from form_filler.date_utils import MONTH_NAMES


def _card(title: str, value: str, color: str = "#2c7be5") -> QFrame:
    """Create a metric card widget."""
    frame = QFrame()
    frame.setFixedSize(150, 90)
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {color};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setAlignment(Qt.AlignCenter)
    layout.setSpacing(4)

    val_lbl = QLabel(value)
    val_lbl.setAlignment(Qt.AlignCenter)
    val_lbl.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")

    ttl_lbl = QLabel(title)
    ttl_lbl.setAlignment(Qt.AlignCenter)
    ttl_lbl.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 12px;")

    layout.addWidget(val_lbl)
    layout.addWidget(ttl_lbl)
    return frame


STATUS_COLORS = {
    "entered":    ("#495057", "#f8f9fa"),
    "delivered":  ("#0c5460", "#d1ecf1"),
    "signed":     ("#155724", "#d4edda"),
    "overdue":    ("#721c24", "#f8d7da"),
    "awaiting_review": ("#856404", "#fff3cd"),
}


class DashboardWindow(QMainWindow):

    open_scanner_requested = Signal()
    open_form_filler_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Eagle Doc Manager — Dashboard")
        self.setMinimumSize(1000, 680)

        self._viewing_month = date.today().month
        self._viewing_year = date.today().year

        tracker.flag_overdue()
        self._build_ui()
        self._refresh()

        # Auto-refresh every 60 seconds
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(60_000)

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ── App header ────────────────────────────────────────
        header_row = QHBoxLayout()

        title = QLabel("Eagle Doc Manager")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a1a2e;")
        header_row.addWidget(title)
        header_row.addStretch()

        scan_btn = QPushButton("📄  Document Scanner")
        scan_btn.setFixedHeight(40)
        scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1a2e; color: white;
                border-radius: 6px; font-size: 13px;
                font-weight: bold; padding: 0 18px;
            }
            QPushButton:hover { background-color: #2c2c54; }
        """)
        scan_btn.clicked.connect(self.open_scanner_requested)
        header_row.addWidget(scan_btn)

        filler_btn = QPushButton("📝  Form Filler")
        filler_btn.setFixedHeight(40)
        filler_btn.setStyleSheet("""
            QPushButton {
                background-color: #2c7be5; color: white;
                border-radius: 6px; font-size: 13px;
                font-weight: bold; padding: 0 18px;
            }
            QPushButton:hover { background-color: #1a68d1; }
        """)
        filler_btn.clicked.connect(self.open_form_filler_requested)
        header_row.addWidget(filler_btn)

        root.addLayout(header_row)

        # ── Divider ───────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #dee2e6;")
        root.addWidget(line)

        # ── Month selector ────────────────────────────────────
        month_row = QHBoxLayout()
        month_row.addWidget(QLabel("Viewing:"))

        self._month_combo = QComboBox()
        self._month_combo.setFixedWidth(160)
        self._month_combo.currentIndexChanged.connect(self._on_month_changed)
        month_row.addWidget(self._month_combo)
        month_row.addStretch()

        self._last_refresh_lbl = QLabel("")
        self._last_refresh_lbl.setStyleSheet("color: #aaa; font-size: 10px;")
        month_row.addWidget(self._last_refresh_lbl)

        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self._refresh)
        month_row.addWidget(refresh_btn)

        root.addLayout(month_row)

        # ── Metric cards ──────────────────────────────────────
        self._cards_layout = QHBoxLayout()
        self._cards_layout.setSpacing(12)

        self._card_overdue   = _card("Overdue", "0", "#dc3545")
        self._card_entered   = _card("Entered", "0", "#6c757d")
        self._card_delivered = _card("Delivered", "0", "#17a2b8")
        self._card_signed    = _card("Signed", "0", "#28a745")
        self._card_review    = _card("Awaiting Review", "0", "#f0ad4e")

        for card in [self._card_overdue, self._card_entered,
                     self._card_delivered, self._card_signed, self._card_review]:
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()
        root.addLayout(self._cards_layout)

        # ── Records table ─────────────────────────────────────
        root.addWidget(QLabel("<b>Forms This Period</b>"))

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Unit", "Tenant", "Building", "Lease Type", "Status", "Awaiting Review", "Created"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table)

        # ── Mark Delivered button ─────────────────────────────
        action_row = QHBoxLayout()
        self._mark_delivered_btn = QPushButton("Mark Selected as Delivered")
        self._mark_delivered_btn.setFixedHeight(34)
        self._mark_delivered_btn.setStyleSheet("""
            QPushButton { background-color: #17a2b8; color: white;
                          border-radius: 4px; font-weight: bold; padding: 0 14px; }
            QPushButton:hover { background-color: #138496; }
        """)
        self._mark_delivered_btn.clicked.connect(self._mark_delivered)
        action_row.addWidget(self._mark_delivered_btn)
        action_row.addStretch()
        root.addLayout(action_row)

    # ── Refresh ───────────────────────────────────────────────

    def _populate_month_combo(self):
        self._month_combo.blockSignals(True)
        self._month_combo.clear()

        today = date.today()
        # Always include current month first
        months = tracker.get_all_months()
        current = (today.month, today.year)
        if current not in months:
            months.insert(0, current)

        self._month_combo.addItem(
            f"{MONTH_NAMES[today.month-1]} {today.year} (Current)",
            userData=(today.month, today.year)
        )
        for m, y in months:
            if (m, y) == current:
                continue
            self._month_combo.addItem(
                f"{MONTH_NAMES[m-1]} {y}", userData=(m, y)
            )

        # Restore selection
        for i in range(self._month_combo.count()):
            data = self._month_combo.itemData(i)
            if data == (self._viewing_month, self._viewing_year):
                self._month_combo.setCurrentIndex(i)
                break

        self._month_combo.blockSignals(False)

    def _refresh(self):
        tracker.flag_overdue()
        self._populate_month_combo()
        self._refresh_metrics()
        self._refresh_table()
        now = date.today()
        self._last_refresh_lbl.setText(
            f"Last refresh: {now.strftime('%H:%M')}"
            if hasattr(date.today(), 'strftime') else ""
        )
        from datetime import datetime
        self._last_refresh_lbl.setText(
            f"Last refresh: {datetime.now().strftime('%H:%M')}"
        )

    def _refresh_metrics(self):
        metrics = tracker.get_metrics(self._viewing_month, self._viewing_year)

        def _update_card(card: QFrame, value: int):
            card.findChildren(QLabel)[0].setText(str(value))

        _update_card(self._card_overdue,   metrics["overdue"])
        _update_card(self._card_entered,   metrics["entered"])
        _update_card(self._card_delivered, metrics["delivered"])
        _update_card(self._card_signed,    metrics["signed"])
        _update_card(self._card_review,    metrics["awaiting_review"])

    def _refresh_table(self):
        records = tracker.get_records_for_month(self._viewing_month, self._viewing_year)
        self._table.setRowCount(len(records))

        for row_i, rec in enumerate(records):
            status = rec.get("status", "entered")
            fg, bg = STATUS_COLORS.get(status, ("#000", "#fff"))

            def _item(text: str) -> QTableWidgetItem:
                item = QTableWidgetItem(str(text))
                item.setBackground(QColor(bg))
                item.setForeground(QColor(fg))
                return item

            self._table.setItem(row_i, 0, _item(rec.get("unit", "")))
            self._table.setItem(row_i, 1, _item(rec.get("tenant_name", "")))
            self._table.setItem(row_i, 2, _item(rec.get("building_addr", "")))
            self._table.setItem(row_i, 3, _item(rec.get("lease_type") or "—"))
            self._table.setItem(row_i, 4, _item(status.title()))
            review = "⚑ Yes" if rec.get("awaiting_review") else ""
            ri = _item(review)
            if rec.get("awaiting_review"):
                ri.setForeground(QColor("#856404"))
            self._table.setItem(row_i, 5, ri)
            created = rec.get("created_at", "")[:10]
            self._table.setItem(row_i, 6, _item(created))

    # ── Actions ───────────────────────────────────────────────

    def _on_month_changed(self, index: int):
        data = self._month_combo.itemData(index)
        if data:
            self._viewing_month, self._viewing_year = data
            self._refresh_metrics()
            self._refresh_table()

    def _mark_delivered(self):
        selected_rows = set(idx.row() for idx in self._table.selectedIndexes())
        if not selected_rows:
            return

        records = tracker.get_records_for_month(self._viewing_month, self._viewing_year)
        for row_i in selected_rows:
            if row_i < len(records):
                rec = records[row_i]
                if rec["status"] in ("entered", "overdue"):
                    tracker.update_record(
                        rec["unit"], rec["month"], rec["year"],
                        status="delivered",
                        delivered_at=str(date.today())
                    )

        self._refresh()

    def notify_batch_complete(self):
        """Called by FormFillerWindow when a new batch is saved."""
        self._viewing_month = date.today().month
        self._viewing_year = date.today().year
        self._refresh()
