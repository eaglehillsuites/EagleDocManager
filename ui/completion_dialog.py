"""
Completion Dialog - Post-processing popup with Undo, Print, Gmail Draft, and Close options.
"""

import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QScrollArea, QWidget,
    QFrame, QSplitter, QGroupBox, QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon


class FileCheckItem(QWidget):
    """Custom widget for a file entry with checkbox."""

    def __init__(self, filename: str, unit: str, form_type: str, source_group: str, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.source_group = source_group

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        layout.addWidget(self.checkbox)

        info_layout = QVBoxLayout()
        name_label = QLabel(f"<b>{filename}</b>")
        name_label.setStyleSheet("font-size: 12px;")
        sub_label = QLabel(f"Unit: {unit}  |  Form: {form_type}")
        sub_label.setStyleSheet("font-size: 10px; color: #666;")
        info_layout.addWidget(name_label)
        info_layout.addWidget(sub_label)
        layout.addLayout(info_layout)
        layout.addStretch()

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class CheckFileListWidget(QWidget):
    """A scrollable list of FileCheckItems with select all/none."""

    def __init__(self, results: list, parent=None):
        super().__init__(parent)
        self.results = results
        self.items: list[FileCheckItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Select all / none
        sel_layout = QHBoxLayout()
        all_btn = QPushButton("Select All")
        none_btn = QPushButton("Select None")
        all_btn.setFixedHeight(28)
        none_btn.setFixedHeight(28)
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        sel_layout.addWidget(all_btn)
        sel_layout.addWidget(none_btn)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # Scroll area for file items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setSpacing(2)

        for r in results:
            if r.get("skipped") or not r.get("generated_file"):
                continue
            item = FileCheckItem(
                filename=r.get("generated_file", ""),
                unit=r.get("unit", ""),
                form_type=r.get("form_type", ""),
                source_group=r.get("original_file", "")
            )
            self.list_layout.addWidget(item)
            self.items.append(item)

        self.list_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _set_all(self, state: bool):
        for item in self.items:
            item.set_checked(state)

    def get_selected(self) -> list[str]:
        """Return filenames of checked items."""
        return [item.filename for item in self.items if item.is_checked()]

    def get_selected_results(self) -> list[dict]:
        """Return full result dicts for checked items."""
        selected_names = set(self.get_selected())
        return [r for r in self.results if r.get("generated_file") in selected_names]


class CompletionDialog(QDialog):
    """
    Post-processing dialog showing:
    - Summary of processed files
    - Undo, Print, Gmail Draft, Close buttons
    """

    def __init__(self, results: list, parent=None):
        super().__init__(parent)
        self.results = [r for r in results if not r.get("skipped")]
        self.setWindowTitle("Processing Complete")
        self.setMinimumSize(620, 500)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Summary header
        success_count = sum(1 for r in self.results if r.get("action") == "Moved")
        header = QLabel(f"<b>✓ Processing Complete</b>  —  {success_count} file(s) processed")
        header.setStyleSheet("font-size: 15px; padding: 8px 0;")
        layout.addWidget(header)

        # File list with checkboxes
        self.file_list = CheckFileListWidget(self.results)
        layout.addWidget(self.file_list)

        # Action buttons
        btn_layout = QHBoxLayout()

        undo_btn = QPushButton("↩ Undo Selected")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet("""
            QPushButton { background-color: #f0ad4e; color: white; border-radius: 4px; font-weight: bold; padding: 0 12px; }
            QPushButton:hover { background-color: #ec971f; }
        """)
        undo_btn.clicked.connect(self._on_undo)

        print_btn = QPushButton("🖨 Print Selected")
        print_btn.setFixedHeight(38)
        print_btn.setStyleSheet("""
            QPushButton { background-color: #5cb85c; color: white; border-radius: 4px; font-weight: bold; padding: 0 12px; }
            QPushButton:hover { background-color: #449d44; }
        """)
        print_btn.clicked.connect(self._on_print)

        gmail_btn = QPushButton("✉ Create Gmail Drafts")
        gmail_btn.setFixedHeight(38)
        gmail_btn.setStyleSheet("""
            QPushButton { background-color: #d9534f; color: white; border-radius: 4px; font-weight: bold; padding: 0 12px; }
            QPushButton:hover { background-color: #c9302c; }
        """)
        gmail_btn.clicked.connect(self._on_gmail)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet("""
            QPushButton { background-color: #aaa; color: white; border-radius: 4px; font-weight: bold; padding: 0 12px; }
            QPushButton:hover { background-color: #888; }
        """)
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(undo_btn)
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(gmail_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _on_undo(self):
        selected = self.file_list.get_selected_results()
        if not selected:
            QMessageBox.information(self, "No Files Selected", "Please select files to undo.")
            return

        from processor import undo_manager
        from processor.audit_logger import log_undo

        # Find undo entries matching the selected results
        recent_entries = undo_manager.get_recent_entries()
        selected_names = {r["original_file"] for r in selected}
        entries_to_undo = [e for e in recent_entries if e["source_filename"] in selected_names]

        if not entries_to_undo:
            QMessageBox.warning(self, "No Undo Data", "No undo data found for selected files.")
            return

        messages = undo_manager.perform_undo(entries_to_undo)
        msg_text = "\n".join(messages)
        QMessageBox.information(self, "Undo Complete", f"Undo completed:\n\n{msg_text}")

    def _on_print(self):
        selected = self.file_list.get_selected_results()
        if not selected:
            QMessageBox.information(self, "No Files Selected", "Please select files to print.")
            return

        errors = []
        for r in selected:
            path = r.get("generated_path", "")
            if path and Path(path).exists():
                try:
                    if sys.platform == "win32":
                        os.startfile(path, "print")
                    else:
                        os.system(f'lp "{path}"')
                except Exception as e:
                    errors.append(f"{r.get('generated_file', '?')}: {e}")
            else:
                errors.append(f"{r.get('generated_file', '?')}: File not found at {path}")

        if errors:
            QMessageBox.warning(self, "Print Errors", "\n".join(errors))

    def _on_gmail(self):
        selected = self.file_list.get_selected_results()
        if not selected:
            QMessageBox.information(self, "No Files Selected", "Please select files for Gmail drafts.")
            return

        try:
            from gmail.gmail_client import create_drafts_for_batch
            progress = QProgressDialog("Creating Gmail drafts...", None, 0, len(selected), self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

            drafts = []
            for i, r in enumerate(selected):
                progress.setValue(i)
                draft = create_drafts_for_batch([r])
                drafts.extend(draft)

            progress.setValue(len(selected))
            QMessageBox.information(self, "Gmail Drafts Created",
                                    f"Created {len(drafts)} draft(s) in Gmail.")
        except Exception as e:
            QMessageBox.critical(self, "Gmail Error",
                                 f"Could not create Gmail drafts:\n{e}\n\n"
                                 "Make sure Gmail is connected in Settings > General.")
