"""
BatchConfirmDialog - Shows all pending processed results before files are moved.

Each row shows:  filename | form type | unit | destination folder
User can click a row to override the destination (one-time or permanent).
Confirm moves everything; Cancel aborts the batch.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QAbstractItemView, QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import config_manager


class BatchConfirmDialog(QDialog):
    """
    pending_items: list of dicts, each with keys:
        filename, form_type, unit, dest_folder, qr_value (optional)
    After exec(), call get_confirmed_items() for the (possibly edited) list.
    """

    def __init__(self, pending_items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Batch — Review Destinations")
        self.setModal(True)
        self.setMinimumSize(820, 400)
        self._items = [dict(i) for i in pending_items]   # deep copy
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Review the destinations below before files are moved.</b><br>"
            "Double-click a destination cell to override it."
        ))

        self._table = QTableWidget(len(self._items), 4)
        self._table.setHorizontalHeaderLabels(["File", "Form Type", "Unit", "Destination Folder"])
        self._table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)

        for row, item in enumerate(self._items):
            self._set_row(row, item)

        self._table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._table)

        # Override-permanently checkbox
        perm_row = QHBoxLayout()
        self._perm_check = QCheckBox(
            "Make destination override permanent (saves as default for this QR code / form type)"
        )
        perm_row.addWidget(self._perm_check)
        perm_row.addStretch()
        layout.addLayout(perm_row)

        # Override button
        override_row = QHBoxLayout()
        override_btn = QPushButton("Override Selected Destination…")
        override_btn.setFixedHeight(30)
        override_btn.clicked.connect(self._override_selected)
        override_row.addWidget(override_btn)
        override_row.addStretch()
        layout.addLayout(override_row)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#dee2e6;")
        layout.addWidget(line)

        # Confirm / Cancel
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel Batch")
        cancel.setFixedHeight(36)
        cancel.clicked.connect(self.reject)

        confirm = QPushButton(f"Confirm & Move {len(self._items)} File(s)")
        confirm.setFixedHeight(36)
        confirm.setStyleSheet("""
            QPushButton {
                background:#2c7be5; color:white;
                border-radius:4px; font-weight:bold; padding:0 16px;
            }
            QPushButton:hover { background:#1a68d1; }
        """)
        confirm.clicked.connect(self._on_confirm)
        btn_row.addWidget(cancel)
        btn_row.addStretch()
        btn_row.addWidget(confirm)
        layout.addLayout(btn_row)

    def _set_row(self, row: int, item: dict):
        def _item(text: str, editable: bool = False) -> QTableWidgetItem:
            ti = QTableWidgetItem(text or "")
            if not editable:
                ti.setFlags(ti.flags() & ~Qt.ItemIsEditable)
            return ti

        self._table.setItem(row, 0, _item(item.get("filename", "")))
        self._table.setItem(row, 1, _item(item.get("form_type", "")))
        self._table.setItem(row, 2, _item(item.get("unit", "")))
        dest_item = _item(item.get("dest_folder", ""), editable=True)
        if not item.get("dest_folder"):
            dest_item.setBackground(QColor("#fff3cd"))
            dest_item.setToolTip("No destination — will be skipped unless overridden")
        self._table.setItem(row, 3, dest_item)

    def _on_item_changed(self, table_item: QTableWidgetItem):
        if table_item.column() == 3:
            row = table_item.row()
            self._items[row]["dest_folder"] = table_item.text().strip()
            self._items[row]["dest_overridden"] = True

    def _override_selected(self):
        rows = set(idx.row() for idx in self._table.selectedIndexes())
        if not rows:
            QMessageBox.information(self, "No Selection", "Select one or more rows first.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if not folder:
            return
        permanent = self._perm_check.isChecked()
        for row in rows:
            self._items[row]["dest_folder"] = folder
            self._items[row]["dest_overridden"] = True
            self._items[row]["dest_permanent"] = permanent
            self._table.blockSignals(True)
            self._table.item(row, 3).setText(folder)
            self._table.blockSignals(False)
            if permanent:
                # Persist the route
                qr = self._items[row].get("qr_value", "")
                if qr:
                    config_manager.save_qr_route(qr, folder)

    def _on_confirm(self):
        # Warn about rows with no destination
        missing = [i for i in self._items if not i.get("dest_folder")]
        if missing:
            names = "\n".join(f"  • {m.get('filename','?')}" for m in missing)
            reply = QMessageBox.question(
                self,
                "Missing Destinations",
                f"The following files have no destination and will be skipped:\n\n{names}\n\n"
                "Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        self.accept()

    def get_confirmed_items(self) -> list[dict]:
        return self._items
