"""
CalendarPopup - A reliable date picker popup for Windows.

Uses QDialog with Qt.FramelessWindowHint + Qt.WindowStaysOnTopHint.
The parent is always the top-level window, keeping a strong reference.
The popup is hidden (not destroyed) after use so it can be reused.
"""

from __future__ import annotations
from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QCalendarWidget, QApplication
)
from PySide6.QtCore import Qt, QDate, Signal, QPoint


class CalendarPopup(QDialog):
    """
    Frameless calendar popup.

    Uses Qt.Popup which gives native "click anywhere outside to close" on all
    platforms. WA_DeleteOnClose is explicitly disabled so we can reuse the
    instance. Parent must always be passed to prevent garbage collection.
    """

    date_selected = Signal(date)

    def __init__(self, parent):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._cal = QCalendarWidget()
        self._cal.setGridVisible(True)
        self._cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self._cal.setNavigationBarVisible(True)
        self._cal.setFixedSize(300, 230)
        self._cal.clicked.connect(self._pick)
        layout.addWidget(self._cal)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())

        self.setStyleSheet("""
            QDialog {
                background: white;
                border: 1px solid #adb5bd;
                border-radius: 4px;
            }
            QCalendarWidget QAbstractItemView {
                color: #212529;
                background: white;
                selection-background-color: #2c7be5;
                selection-color: white;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2c7be5;
            }
            QCalendarWidget QToolButton {
                color: white;
                background: transparent;
                font-weight: bold;
                font-size: 11px;
            }
            QCalendarWidget QMenu { color: #212529; background: white; }
            QCalendarWidget QSpinBox { color: white; background: transparent; }
            QCalendarWidget QAbstractItemView:disabled { color: #adb5bd; }
        """)

    def show_for(self, current: date, anchor_widget):
        """
        Display the calendar pre-selected to `current`, positioned
        just below `anchor_widget`.
        """
        self._cal.setSelectedDate(QDate(current.year, current.month, current.day))
        self._cal.showSelectedDate()

        # Calculate screen position
        screen = QApplication.primaryScreen().availableGeometry()
        bottom_left = anchor_widget.mapToGlobal(
            QPoint(0, anchor_widget.height() + 2)
        )
        x = bottom_left.x()
        y = bottom_left.y()
        w = self.width()
        h = self.height()

        # Clamp to screen
        if x + w > screen.right():
            x = screen.right() - w - 4
        if x < screen.left():
            x = screen.left() + 4
        if y + h > screen.bottom():
            # Flip above the button
            y = anchor_widget.mapToGlobal(QPoint(0, -h - 2)).y()
        if y < screen.top():
            y = screen.top() + 4

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _pick(self, qdate: QDate):
        picked = date(qdate.year(), qdate.month(), qdate.day())
        self.hide()
        self.date_selected.emit(picked)

    def keyPressEvent(self, event):
        """Close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    # Qt.Popup handles click-outside-to-close natively
