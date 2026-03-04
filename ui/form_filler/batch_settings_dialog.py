"""
Batch Settings Dialog

Each date field: [ dd/mm/yyyy input ] [ 📅 button ]
Auto-calculated fields start greyed. Clicking prompts before unlocking.
Lease Start is a month dropdown only.
No horizontal scrollbar.
"""

from __future__ import annotations
import calendar as _cal
from datetime import date

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QScrollArea, QWidget,
    QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from ui.form_filler.calendar_popup import CalendarPopup
from form_filler.date_utils import (
    MONTH_NAMES, default_due_date, default_delivery_date,
    most_recent_past_month_start, lease_end_from_start,
    new_lease_end_from_end, increase_date_from_lease_start,
    ordinal_date_str, month_year_str,
)


# ── Date formatting ───────────────────────────────────────────

def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _parse(text: str) -> date | None:
    try:
        d, m, y = text.strip().split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


_STYLE_LOCKED   = ("background:#e9ecef; color:#6c757d; "
                   "border:1px solid #ced4da; border-radius:4px; padding:3px 6px;")
_STYLE_NORMAL   = ("background:white; color:#212529; "
                   "border:1px solid #ced4da; border-radius:4px; padding:3px 6px;")
_STYLE_ERROR    = ("background:white; color:#212529; "
                   "border:1px solid #dc3545; border-radius:4px; padding:3px 6px;")


# ── Date field widget ─────────────────────────────────────────

class _DateField(QWidget):
    """
    [ dd/mm/yyyy ] [ 📅 ]

    auto_calculated=True  →  greyed out, click to unlock with confirmation.
    The CalendarPopup is created once, parented to the top-level dialog,
    and reused for every open — never destroyed.
    """
    date_changed = Signal(date)

    # Shared popup per top-level dialog, set after creation
    _shared_popup: CalendarPopup | None = None

    def __init__(self, initial: date, auto_calculated: bool = False,
                 dialog_ref=None, parent=None):
        super().__init__(parent)
        self._date = initial
        self._locked = auto_calculated
        self._dialog_ref = dialog_ref   # reference to parent QDialog for popup

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._input = QLineEdit(_fmt(initial))
        self._input.setPlaceholderText("dd/mm/yyyy")
        self._input.setFixedWidth(105)
        self._input.setReadOnly(auto_calculated)
        self._input.setStyleSheet(_STYLE_LOCKED if auto_calculated else _STYLE_NORMAL)
        self._input.mousePressEvent = self._input_clicked
        self._input.editingFinished.connect(self._text_done)
        row.addWidget(self._input)

        self._btn = QPushButton("📅")
        self._btn.setFixedSize(30, 28)
        self._btn.setToolTip("Pick date")
        self._btn.setEnabled(not auto_calculated)
        self._btn.setStyleSheet("""
            QPushButton {
                border:1px solid #ced4da; border-radius:4px;
                background:#f8f9fa; font-size:14px; padding:0;
            }
            QPushButton:hover:enabled { background:#e2e8f0; }
            QPushButton:disabled { color:#adb5bd; background:#f0f0f0; }
        """)
        self._btn.clicked.connect(self._open_cal)
        row.addWidget(self._btn)
        row.addStretch()

    # ── Unlock ────────────────────────────────────────────────

    def _input_clicked(self, event):
        if self._locked:
            self._prompt_unlock()
        else:
            QLineEdit.mousePressEvent(self._input, event)

    def _prompt_unlock(self):
        ans = QMessageBox.question(
            self,
            "Override Auto-Calculated Value",
            "This value is auto-calculated.\n\nAre you sure you want to override it?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self._locked = False
            self._input.setReadOnly(False)
            self._input.setStyleSheet(_STYLE_NORMAL)
            self._btn.setEnabled(True)
            self._input.setFocus()
            self._input.selectAll()
        else:
            # Explicitly re-apply locked style in case Qt cleared it during the msgbox
            self._input.setReadOnly(True)
            self._input.setStyleSheet(_STYLE_LOCKED)
            self._btn.setEnabled(False)

    # ── Calendar ──────────────────────────────────────────────

    def _get_popup(self) -> CalendarPopup:
        """Get (or lazily create) the shared popup for this dialog."""
        dlg = self._dialog_ref
        if dlg is None:
            # Fallback — use self as parent
            dlg = self
        if dlg._popup is None:
            dlg._popup = CalendarPopup(dlg)
        return dlg._popup

    def _open_cal(self):
        popup = self._get_popup()
        # Disconnect any previous field's signal
        try:
            popup.date_selected.disconnect()
        except Exception:
            pass
        popup.date_selected.connect(self._cal_picked)
        current = _parse(self._input.text()) or self._date
        popup.show_for(current, self._btn)

    def _cal_picked(self, d: date):
        self._date = d
        self._input.setText(_fmt(d))
        self._input.setStyleSheet(_STYLE_NORMAL)
        self.date_changed.emit(d)

    # ── Text ──────────────────────────────────────────────────

    def _text_done(self):
        d = _parse(self._input.text())
        if d:
            self._date = d
            self._input.setStyleSheet(_STYLE_NORMAL)
            self.date_changed.emit(d)
        else:
            self._input.setStyleSheet(_STYLE_ERROR)

    # ── Public API ────────────────────────────────────────────

    def get_date(self) -> date | None:
        d = _parse(self._input.text())
        if d:
            self._date = d
        return self._date if d else None

    def set_date(self, d: date):
        """Update only if still locked (auto-calculated, not overridden)."""
        if self._locked:
            self._date = d
            self._input.setText(_fmt(d))


# ── Layout helpers ────────────────────────────────────────────

def _row(label: str, widget: QWidget, note: str = "") -> QHBoxLayout:
    lbl = QLabel(label)
    lbl.setFixedWidth(160)
    lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    h = QHBoxLayout()
    h.setSpacing(8)
    h.addWidget(lbl)
    h.addWidget(widget)
    if note:
        n = QLabel(note)
        n.setStyleSheet("color:#888; font-size:10px;")
        h.addWidget(n)
    h.addStretch()
    return h


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background:#dee2e6; max-height:1px; margin:6px 0;")
    return f


def _section(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        "font-weight:bold; font-size:12px; color:#1a1a2e; padding:4px 0 2px 0;"
    )
    return l


def _hint(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color:#6c757d; font-size:10px; padding-bottom:4px;")
    l.setWordWrap(True)
    return l


# ── Dialog ────────────────────────────────────────────────────

class BatchSettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Settings — Form Filler")
        self.setMinimumWidth(520)
        self.setMaximumWidth(620)
        self.setModal(True)

        # Single shared CalendarPopup for all fields — created lazily
        self._popup: CalendarPopup | None = None

        today = date.today()
        self._today = today
        self._result: dict | None = None
        self._combo_months: list[int] = []

        self._delivery    = default_delivery_date()
        self._due         = default_due_date()
        self._lease_start = most_recent_past_month_start(today.month)
        self._lease_end   = lease_end_from_start(self._lease_start)
        self._new_end     = new_lease_end_from_end(self._lease_end)
        self._inc_date    = increase_date_from_lease_start(self._lease_start)

        self._build_ui()

    def _make_field(self, d: date, auto: bool = False) -> "_DateField":
        return _DateField(d, auto_calculated=auto, dialog_ref=self)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        body = QWidget()
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(6)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # ── Delivery Date ──────────────────────────────────────
        layout.addWidget(_section("Delivery Date"))
        layout.addWidget(_hint("The date you plan to deliver the notice. Defaults to today."))
        self._f_delivery = self._make_field(self._delivery, auto=False)
        self._f_delivery.date_changed.connect(lambda d: setattr(self, "_delivery", d))
        layout.addLayout(_row("Delivery Date:", self._f_delivery))

        layout.addWidget(_divider())

        # ── Renewal Dates ──────────────────────────────────────
        layout.addWidget(_section("Renewal Date Fields"))
        layout.addWidget(_hint(
            "Auto-calculated fields are greyed out. "
            "Click any field to override it."
        ))

        # Lease Start month dropdown
        self._combo = QComboBox()
        self._combo.setFixedWidth(148)
        self._build_combo()
        self._combo.currentIndexChanged.connect(self._on_combo)
        layout.addLayout(_row("Lease Start Month:", self._combo))

        # All remaining fields are auto-calculated
        self._f_ls  = self._make_field(self._lease_start, auto=True)
        self._f_le  = self._make_field(self._lease_end,   auto=True)
        self._f_ne  = self._make_field(self._new_end,     auto=True)
        self._f_id  = self._make_field(self._inc_date,    auto=True)
        self._f_due = self._make_field(self._due,         auto=True)

        self._f_ls.date_changed.connect(self._on_ls_changed)
        self._f_le.date_changed.connect(self._on_le_changed)
        self._f_ne.date_changed.connect(lambda d: setattr(self, "_new_end", d))
        self._f_id.date_changed.connect(lambda d: setattr(self, "_inc_date", d))
        self._f_due.date_changed.connect(lambda d: setattr(self, "_due", d))

        layout.addLayout(_row("Lease Start Date:", self._f_ls,  "(auto: 1st of month)"))
        layout.addLayout(_row("Lease End:",        self._f_le,  "(auto: 1 year − 1 day)"))
        layout.addLayout(_row("New End of Lease:", self._f_ne,  "(auto: Lease End + 1 year)"))
        layout.addLayout(_row("Increase Date:",    self._f_id,  "(auto: Lease Start + 1 year)"))
        layout.addLayout(_row("Due Date:",         self._f_due, "(auto: last day of next month)"))

        layout.addStretch()

        # ── Footer ────────────────────────────────────────────
        outer.addWidget(_divider())
        foot = QHBoxLayout()
        foot.setContentsMargins(20, 8, 20, 12)

        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36)
        cancel.clicked.connect(self.reject)

        confirm = QPushButton("Confirm & Begin Processing")
        confirm.setFixedHeight(36)
        confirm.setStyleSheet("""
            QPushButton {
                background-color:#2c7be5; color:white;
                border-radius:4px; font-weight:bold; padding:0 16px;
            }
            QPushButton:hover { background-color:#1a68d1; }
        """)
        confirm.clicked.connect(self._on_confirm)

        foot.addWidget(cancel)
        foot.addStretch()
        foot.addWidget(confirm)
        outer.addLayout(foot)

    # ── Combo ─────────────────────────────────────────────────

    def _build_combo(self):
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo_months.clear()
        start = self._today.month
        for m in list(range(start, 13)) + list(range(1, start)):
            self._combo.addItem(MONTH_NAMES[m - 1])
            self._combo_months.append(m)
        self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

    def _on_combo(self, index: int):
        self._lease_start = most_recent_past_month_start(self._combo_months[index])
        self._f_ls.set_date(self._lease_start)
        self._cascade(self._lease_start)

    def _on_ls_changed(self, d: date):
        self._lease_start = d
        self._cascade(d)

    def _cascade(self, ls: date):
        self._lease_end = lease_end_from_start(ls)
        self._new_end   = new_lease_end_from_end(self._lease_end)
        self._inc_date  = increase_date_from_lease_start(ls)
        self._f_le.set_date(self._lease_end)
        self._f_ne.set_date(self._new_end)
        self._f_id.set_date(self._inc_date)

    def _on_le_changed(self, d: date):
        self._lease_end = d
        self._new_end   = new_lease_end_from_end(d)
        self._f_ne.set_date(self._new_end)

    # ── Confirm ───────────────────────────────────────────────

    def _on_confirm(self):
        fields = {
            "Delivery Date":    self._f_delivery,
            "Lease Start Date": self._f_ls,
            "Lease End":        self._f_le,
            "New End of Lease": self._f_ne,
            "Increase Date":    self._f_id,
            "Due Date":         self._f_due,
        }
        errors, resolved = [], {}
        for name, field in fields.items():
            d = field.get_date()
            if d is None:
                errors.append(f"• {name}")
            else:
                resolved[name] = d

        if errors:
            QMessageBox.warning(self, "Invalid Dates",
                                "Fix the following fields:\n\n" + "\n".join(errors))
            return

        self._result = {
            "delivery_date": ordinal_date_str(resolved["Delivery Date"]),
            "due_date":      ordinal_date_str(resolved["Due Date"]),
            "lease_start":   ordinal_date_str(resolved["Lease Start Date"]),
            "lease_end":     ordinal_date_str(resolved["Lease End"]),
            "new_lease_end": month_year_str(resolved["New End of Lease"]),
            "increase_date": ordinal_date_str(resolved["Increase Date"]),
            "_delivery_date_obj": resolved["Delivery Date"],
            "_increase_year":     resolved["Increase Date"].year,
        }
        self.accept()

    def get_result(self) -> dict | None:
        return self._result
