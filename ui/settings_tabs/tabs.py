"""
Settings Tabs - All settings tab widgets for the main settings window.
"""

import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QFileDialog, QCheckBox, QComboBox,
    QGroupBox, QFormLayout, QInputDialog, QMessageBox, QScrollArea,
    QFrame, QAbstractItemView, QSplitter, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

import config_manager


# ─────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────

def folder_picker(parent, title="Select Folder") -> str:
    return QFileDialog.getExistingDirectory(parent, title)


def styled_button(text: str, color: str = "#2c7be5") -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(32)
    btn.setStyleSheet(f"""
        QPushButton {{ background-color: {color}; color: white; border-radius: 4px;
                       font-weight: bold; padding: 0 10px; }}
        QPushButton:hover {{ opacity: 0.85; }}
        QPushButton:disabled {{ background-color: #ccc; color: #888; }}
    """)
    return btn


# ─────────────────────────────────────────
#  GENERAL TAB
# ─────────────────────────────────────────

class GeneralTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Tenant Root
        tenant_row = QHBoxLayout()
        self.tenant_root = QLineEdit()
        self.tenant_root.setPlaceholderText("e.g., C:\\Tenants")
        browse_tenant = QPushButton("Browse...")
        browse_tenant.clicked.connect(lambda: self._pick_folder(self.tenant_root))
        tenant_row.addWidget(self.tenant_root)
        tenant_row.addWidget(browse_tenant)
        form.addRow("Tenant Folder Root:", tenant_row)

        # Previous Tenants Path
        prev_row = QHBoxLayout()
        self.prev_tenants = QLineEdit()
        self.prev_tenants.setPlaceholderText("e.g., C:\\Tenants\\Previous Tenants")
        browse_prev = QPushButton("Browse...")
        browse_prev.clicked.connect(lambda: self._pick_folder(self.prev_tenants))
        prev_row.addWidget(self.prev_tenants)
        prev_row.addWidget(browse_prev)
        form.addRow("Previous Tenants Path:", prev_row)

        layout.addLayout(form)
        layout.addSpacing(12)

        # Start with windows
        self.start_windows = QCheckBox("Start EagleDocManager with Windows")
        layout.addWidget(self.start_windows)

        layout.addSpacing(12)

        # Gmail section
        gmail_group = QGroupBox("Gmail Integration")
        gmail_layout = QVBoxLayout(gmail_group)

        self.gmail_status = QLabel("Status: Not connected")
        self.gmail_status.setStyleSheet("color: #888;")
        gmail_layout.addWidget(self.gmail_status)

        gmail_btn_layout = QHBoxLayout()
        self.connect_btn = styled_button("Connect Gmail", "#d9534f")
        self.connect_btn.clicked.connect(self._connect_gmail)
        self.disconnect_btn = styled_button("Disconnect", "#aaa")
        self.disconnect_btn.clicked.connect(self._disconnect_gmail)
        gmail_btn_layout.addWidget(self.connect_btn)
        gmail_btn_layout.addWidget(self.disconnect_btn)
        gmail_btn_layout.addStretch()
        gmail_layout.addLayout(gmail_btn_layout)

        layout.addWidget(gmail_group)
        layout.addStretch()

        save_btn = styled_button("Save General Settings")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _pick_folder(self, target: QLineEdit):
        path = folder_picker(self)
        if path:
            target.setText(path)

    def _load(self):
        cfg = config_manager.load_config()
        self.tenant_root.setText(cfg.get("tenant_root", ""))
        self.prev_tenants.setText(cfg.get("previous_tenants_path", ""))
        self.start_windows.setChecked(cfg.get("start_with_windows", False))
        self._update_gmail_status()

    def _update_gmail_status(self):
        try:
            from gmail.gmail_client import is_connected
            if is_connected():
                self.gmail_status.setText("Status: ✓ Connected")
                self.gmail_status.setStyleSheet("color: green; font-weight: bold;")
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
            else:
                self.gmail_status.setText("Status: Not connected")
                self.gmail_status.setStyleSheet("color: #888;")
                self.connect_btn.setEnabled(True)
                self.disconnect_btn.setEnabled(False)
        except Exception:
            self.gmail_status.setText("Status: Gmail library not available")

    def _connect_gmail(self):
        try:
            from gmail.gmail_client import get_credentials
            get_credentials()
            self._update_gmail_status()
            QMessageBox.information(self, "Gmail", "Successfully connected to Gmail!")
        except Exception as e:
            QMessageBox.critical(self, "Gmail Error", f"Could not connect:\n{e}")

    def _disconnect_gmail(self):
        from gmail.gmail_client import disconnect
        disconnect()
        self._update_gmail_status()

    def _save(self):
        cfg = config_manager.load_config()
        cfg["tenant_root"] = self.tenant_root.text().strip()
        cfg["previous_tenants_path"] = self.prev_tenants.text().strip()
        cfg["start_with_windows"] = self.start_windows.isChecked()
        config_manager.save_config(cfg)
        QMessageBox.information(self, "Saved", "General settings saved.")


# ─────────────────────────────────────────
#  AUTO SCAN TAB
# ─────────────────────────────────────────

class AutoScanTab(QWidget):
    watcher_status_changed = Signal(bool)  # True=running, False=paused

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Watched Folders
        folders_group = QGroupBox("Watched Folders")
        folders_layout = QVBoxLayout(folders_group)

        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(120)
        folders_layout.addWidget(self.folder_list)

        fl_btns = QHBoxLayout()
        add_folder_btn = styled_button("+ Add Folder")
        add_folder_btn.clicked.connect(self._add_folder)
        remove_folder_btn = styled_button("Remove Selected", "#d9534f")
        remove_folder_btn.clicked.connect(self._remove_folder)
        fl_btns.addWidget(add_folder_btn)
        fl_btns.addWidget(remove_folder_btn)
        fl_btns.addStretch()
        folders_layout.addLayout(fl_btns)
        layout.addWidget(folders_group)

        # Exceptions
        exc_group = QGroupBox("Exceptions (filenames containing these words will be ignored)")
        exc_layout = QVBoxLayout(exc_group)

        self.exc_list = QListWidget()
        self.exc_list.setMaximumHeight(100)
        exc_layout.addWidget(self.exc_list)

        exc_btns = QHBoxLayout()
        add_exc = styled_button("+ Add Exception")
        add_exc.clicked.connect(self._add_exception)
        remove_exc = styled_button("Remove Selected", "#d9534f")
        remove_exc.clicked.connect(self._remove_exception)
        exc_btns.addWidget(add_exc)
        exc_btns.addWidget(remove_exc)
        exc_btns.addStretch()
        exc_layout.addLayout(exc_btns)
        layout.addWidget(exc_group)

        # Scan mode
        mode_group = QGroupBox("Default Scan Mode")
        mode_layout = QVBoxLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Mode 1 — One document per PDF",
            "Mode 2 — Multiple documents per PDF (QR on each first page)",
            "Mode 3 — Separator pages method"
        ])
        mode_layout.addWidget(self.mode_combo)
        layout.addWidget(mode_group)

        # Watcher controls
        watcher_group = QGroupBox("Watcher Control")
        watcher_layout = QHBoxLayout(watcher_group)
        self.watcher_status_label = QLabel("Watcher: Stopped")
        self.watcher_status_label.setStyleSheet("font-weight: bold;")
        self.pause_btn = styled_button("Pause Watcher", "#f0ad4e")
        self.pause_btn.setEnabled(False)
        self.resume_btn = styled_button("Resume Watcher", "#5cb85c")
        self.pause_btn.clicked.connect(self._pause_watcher)
        self.resume_btn.clicked.connect(self._resume_watcher)
        watcher_layout.addWidget(self.watcher_status_label)
        watcher_layout.addStretch()
        watcher_layout.addWidget(self.pause_btn)
        watcher_layout.addWidget(self.resume_btn)
        layout.addWidget(watcher_group)

        save_btn = styled_button("Save Auto Scan Settings")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _load(self):
        cfg = config_manager.load_config()
        self.folder_list.clear()
        for f in cfg.get("watched_folders", []):
            self.folder_list.addItem(f)
        self.exc_list.clear()
        for e in cfg.get("exceptions", []):
            self.exc_list.addItem(e)
        mode = cfg.get("scan_mode", 1) - 1
        self.mode_combo.setCurrentIndex(max(0, min(2, mode)))

    def _add_folder(self):
        path = folder_picker(self, "Add Watched Folder")
        if path and path not in [self.folder_list.item(i).text()
                                   for i in range(self.folder_list.count())]:
            self.folder_list.addItem(path)

    def _remove_folder(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def _add_exception(self):
        text, ok = QInputDialog.getText(self, "Add Exception", "Enter keyword:")
        if ok and text.strip():
            self.exc_list.addItem(text.strip())

    def _remove_exception(self):
        for item in self.exc_list.selectedItems():
            self.exc_list.takeItem(self.exc_list.row(item))

    def _pause_watcher(self):
        self.watcher_status_changed.emit(False)
        self.watcher_status_label.setText("Watcher: ⏸ Paused")
        self.watcher_status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)

    def _resume_watcher(self):
        self.watcher_status_changed.emit(True)
        self.watcher_status_label.setText("Watcher: ▶ Running")
        self.watcher_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)

    def set_watcher_running(self, running: bool):
        if running:
            self.watcher_status_label.setText("Watcher: ▶ Running")
            self.watcher_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
        else:
            self.watcher_status_label.setText("Watcher: ⏸ Paused")
            self.watcher_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)

    def _save(self):
        cfg = config_manager.load_config()
        cfg["watched_folders"] = [
            self.folder_list.item(i).text() for i in range(self.folder_list.count())
        ]
        cfg["exceptions"] = [
            self.exc_list.item(i).text() for i in range(self.exc_list.count())
        ]
        cfg["scan_mode"] = self.mode_combo.currentIndex() + 1
        config_manager.save_config(cfg)
        QMessageBox.information(self, "Saved", "Auto Scan settings saved.")


# ─────────────────────────────────────────
#  MANUAL SCAN TAB
# ─────────────────────────────────────────

class ManualScanTab(QWidget):
    process_folder_requested = Signal(str, int)  # folder_path, mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        folder_group = QGroupBox("Select Folder to Process")
        folder_layout = QVBoxLayout(folder_group)

        path_row = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText("Select a folder containing PDFs...")
        self.folder_path.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._pick_folder)
        path_row.addWidget(self.folder_path)
        path_row.addWidget(browse_btn)
        folder_layout.addLayout(path_row)
        layout.addWidget(folder_group)

        mode_group = QGroupBox("Scan Mode for this Batch")
        mode_layout = QVBoxLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Mode 1 — One document per PDF",
            "Mode 2 — Multiple documents per PDF (QR on each first page)",
            "Mode 3 — Separator pages method"
        ])
        # Load default from config
        cfg = config_manager.load_config()
        self.mode_combo.setCurrentIndex(cfg.get("scan_mode", 1) - 1)
        mode_layout.addWidget(self.mode_combo)
        layout.addWidget(mode_group)

        process_btn = styled_button("▶  Process Folder", "#5cb85c")
        process_btn.setFixedHeight(44)
        process_btn.clicked.connect(self._on_process)
        layout.addWidget(process_btn)

        # Log area
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        log_layout.addWidget(self.log_area)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_area.clear)
        log_layout.addWidget(clear_log_btn)

        layout.addWidget(log_group)

    def _pick_folder(self):
        path = folder_picker(self, "Select Folder to Process")
        if path:
            self.folder_path.setText(path)

    def _on_process(self):
        path = self.folder_path.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "No Folder", "Please select a valid folder.")
            return
        mode = self.mode_combo.currentIndex() + 1
        self.log_area.append(f"Starting processing of: {path}")
        self.process_folder_requested.emit(path, mode)

    def append_log(self, message: str):
        self.log_area.append(message)


# ─────────────────────────────────────────
#  FORMS TAB
# ─────────────────────────────────────────

class FormsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_form = None
        self._build_ui()
        self._load_forms()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: list
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Form Types</b>"))
        self.form_list = QListWidget()
        self.form_list.setMinimumWidth(180)
        self.form_list.currentRowChanged.connect(self._on_form_selected)
        left.addWidget(self.form_list)

        add_btn = styled_button("+ Add Form Type")
        add_btn.clicked.connect(self._add_form)
        left.addWidget(add_btn)
        layout.addLayout(left)

        # Right: editor
        right = QVBoxLayout()
        self.editor_group = QGroupBox("Edit Form Type")
        self.editor_group.setEnabled(False)
        editor_layout = QFormLayout(self.editor_group)

        self.form_name_input = QLineEdit()
        editor_layout.addRow("Form Name:", self.form_name_input)

        self.dm_value_input = QLineEdit()
        self.dm_value_input.setPlaceholderText("e.g., FORM:Maintenance")
        editor_layout.addRow("Data Matrix Value:", self.dm_value_input)

        self.profile_combo = QComboBox()
        editor_layout.addRow("Naming Convention:", self.profile_combo)

        # OCR Keywords
        ocr_label = QLabel("OCR Title Keywords:")
        editor_layout.addRow(ocr_label)

        ocr_hint = QLabel(
            "One keyword group per line. Words separated by commas = AND logic "
            "(all must appear). Multiple lines = OR logic (any line can match). "
            "Case-insensitive."
        )
        ocr_hint.setWordWrap(True)
        ocr_hint.setStyleSheet("color: #666; font-size: 10px;")
        editor_layout.addRow(ocr_hint)

        self.ocr_keywords_input = QTextEdit()
        self.ocr_keywords_input.setPlaceholderText(
            "Examples:\nINCREASE OF RENT\nMEMORANDUM, INCREASE\nRENT INCREASE"
        )
        self.ocr_keywords_input.setFixedHeight(100)
        editor_layout.addRow(self.ocr_keywords_input)

        save_form_btn = styled_button("Save Changes")
        save_form_btn.clicked.connect(self._save_form)
        editor_layout.addRow("", save_form_btn)

        delete_btn = styled_button("Delete This Form Type", "#d9534f")
        delete_btn.clicked.connect(self._delete_form)
        editor_layout.addRow("", delete_btn)

        right.addWidget(self.editor_group)
        right.addStretch()
        layout.addLayout(right)

        self._refresh_profile_combo()

    def _refresh_profile_combo(self):
        self.profile_combo.clear()
        profiles = config_manager.load_naming_profiles()
        for p in profiles:
            self.profile_combo.addItem(p["name"], p["id"])

    def _load_forms(self):
        self.form_list.clear()
        forms = config_manager.load_forms()
        for f in forms:
            self.form_list.addItem(f["name"])

    def _on_form_selected(self, index: int):
        forms = config_manager.load_forms()
        if index < 0 or index >= len(forms):
            self.editor_group.setEnabled(False)
            return

        self._selected_form = forms[index]
        self.editor_group.setEnabled(True)
        self.form_name_input.setText(self._selected_form.get("name", ""))
        self.dm_value_input.setText(self._selected_form.get("datamatrix_value", ""))

        prof_id = self._selected_form.get("naming_profile_id", "")
        idx = self.profile_combo.findData(prof_id)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

        # Populate OCR keywords — one group per line, keywords comma-separated
        kw_groups = self._selected_form.get("ocr_keywords", [])
        lines = []
        for group in kw_groups:
            if isinstance(group, list):
                lines.append(", ".join(group))
            else:
                lines.append(str(group))
        self.ocr_keywords_input.setPlainText("\n".join(lines))

    def _add_form(self):
        name, ok = QInputDialog.getText(self, "New Form Type", "Form name:")
        if ok and name.strip():
            forms = config_manager.load_forms()
            new_form = {
                "id": name.lower().replace(" ", "_"),
                "name": name.strip(),
                "datamatrix_value": f"FORM:{name.replace(' ', '')}",
                "naming_profile_id": "default_profile"
            }
            forms.append(new_form)
            config_manager.save_forms(forms)
            self._load_forms()
            self.form_list.setCurrentRow(len(forms) - 1)

    def _save_form(self):
        if not self._selected_form:
            return
        # Parse OCR keywords from the text area
        raw_lines = self.ocr_keywords_input.toPlainText().strip().splitlines()
        ocr_keywords = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip().upper() for p in line.split(",") if p.strip()]
            if len(parts) == 1:
                ocr_keywords.append(parts[0])  # Single string for simple keywords
            elif len(parts) > 1:
                ocr_keywords.append(parts)     # List for AND-logic groups

        forms = config_manager.load_forms()
        for i, f in enumerate(forms):
            if f.get("id") == self._selected_form.get("id"):
                forms[i]["name"] = self.form_name_input.text().strip()
                forms[i]["datamatrix_value"] = self.dm_value_input.text().strip()
                forms[i]["naming_profile_id"] = self.profile_combo.currentData() or "default_profile"
                forms[i]["ocr_keywords"] = ocr_keywords
                break
        config_manager.save_forms(forms)
        self._load_forms()
        QMessageBox.information(self, "Saved", "Form type saved.")

    def _delete_form(self):
        if not self._selected_form:
            return
        reply = QMessageBox.question(self, "Delete Form",
                                     f"Delete '{self._selected_form['name']}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            forms = config_manager.load_forms()
            forms = [f for f in forms if f.get("id") != self._selected_form.get("id")]
            config_manager.save_forms(forms)
            self._selected_form = None
            self.editor_group.setEnabled(False)
            self._load_forms()


# ─────────────────────────────────────────
#  NAMING CONVENTIONS TAB
# ─────────────────────────────────────────

class NamingConventionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_profile = None
        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: list
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Naming Profiles</b>"))
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(180)
        self.profile_list.currentRowChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self.profile_list)

        add_profile_btn = styled_button("+ Add Profile")
        add_profile_btn.clicked.connect(self._add_profile)
        left_layout.addWidget(add_profile_btn)
        layout.addLayout(left_layout)

        # Right: editor
        right_layout = QVBoxLayout()

        self.editor_group = QGroupBox("Edit Naming Convention")
        self.editor_group.setEnabled(False)
        editor_layout = QVBoxLayout(self.editor_group)

        form = QFormLayout()
        self.profile_name_input = QLineEdit()
        form.addRow("Profile Name:", self.profile_name_input)

        self.date_format_input = QLineEdit()
        self.date_format_input.setPlaceholderText("e.g., yyyy-mm-dd or mmmYYYY")
        form.addRow("Date Format:", self.date_format_input)

        date_hint = QLabel("Tokens: yyyy YYYY mm dd mmm  →  2026 2026 02 26 Feb")
        date_hint.setStyleSheet("color: #888; font-size: 10px;")
        form.addRow("", date_hint)
        editor_layout.addLayout(form)

        # Parts list
        editor_layout.addWidget(QLabel("<b>File Naming Parts:</b>"))

        self.parts_list = QListWidget()
        self.parts_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.parts_list.setMinimumHeight(160)
        editor_layout.addWidget(self.parts_list)

        parts_btn_layout = QHBoxLayout()
        add_part_btn = styled_button("+ Add Part")
        add_part_btn.clicked.connect(self._add_part)
        edit_part_btn = styled_button("Edit Part", "#5cb85c")
        edit_part_btn.clicked.connect(self._edit_part)
        del_part_btn = styled_button("Delete Part", "#d9534f")
        del_part_btn.clicked.connect(self._delete_part)
        parts_btn_layout.addWidget(add_part_btn)
        parts_btn_layout.addWidget(edit_part_btn)
        parts_btn_layout.addWidget(del_part_btn)
        editor_layout.addLayout(parts_btn_layout)

        # Preview
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))
        self.preview_label = QLabel("<i>Configure parts above</i>")
        self.preview_label.setStyleSheet("color: #444; font-style: italic;")
        preview_layout.addWidget(self.preview_label)
        editor_layout.addLayout(preview_layout)

        save_btn = styled_button("Save Profile")
        save_btn.clicked.connect(self._save_profile)
        editor_layout.addWidget(save_btn)

        delete_btn = styled_button("Delete Profile", "#d9534f")
        delete_btn.clicked.connect(self._delete_profile)
        editor_layout.addWidget(delete_btn)

        right_layout.addWidget(self.editor_group)
        right_layout.addStretch()
        layout.addLayout(right_layout)

    def _load_profiles(self):
        self.profile_list.clear()
        profiles = config_manager.load_naming_profiles()
        for p in profiles:
            self.profile_list.addItem(p["name"])

    def _on_profile_selected(self, index: int):
        profiles = config_manager.load_naming_profiles()
        if index < 0 or index >= len(profiles):
            self.editor_group.setEnabled(False)
            return

        self._selected_profile = profiles[index]
        self.editor_group.setEnabled(True)
        self.profile_name_input.setText(self._selected_profile.get("name", ""))
        self.date_format_input.setText(self._selected_profile.get("date_format", "yyyy-mm-dd"))

        self.parts_list.clear()
        from ui.part_editor import part_to_display
        for part in self._selected_profile.get("parts", []):
            self.parts_list.addItem(part_to_display(part))

        self._update_preview()

    def _get_current_parts(self) -> list:
        """Get parts from the parts list widget using stored data."""
        if not self._selected_profile:
            return []
        return list(self._selected_profile.get("parts", []))

    def _add_part(self):
        if not self._selected_profile:
            return
        from ui.part_editor import PartEditorDialog, part_to_display
        dialog = PartEditorDialog(parent=self)
        if dialog.exec():
            part = dialog.get_part()
            if part:
                if "parts" not in self._selected_profile:
                    self._selected_profile["parts"] = []
                self._selected_profile["parts"].append(part)
                self.parts_list.addItem(part_to_display(part))
                self._update_preview()

    def _edit_part(self):
        idx = self.parts_list.currentRow()
        if idx < 0 or not self._selected_profile:
            return
        parts = self._selected_profile.get("parts", [])
        if idx >= len(parts):
            return
        from ui.part_editor import PartEditorDialog, part_to_display
        dialog = PartEditorDialog(existing_part=parts[idx], parent=self)
        if dialog.exec():
            new_part = dialog.get_part()
            if new_part:
                parts[idx] = new_part
                self._selected_profile["parts"] = parts
                self.parts_list.item(idx).setText(part_to_display(new_part))
                self._update_preview()

    def _delete_part(self):
        idx = self.parts_list.currentRow()
        if idx < 0 or not self._selected_profile:
            return
        self.parts_list.takeItem(idx)
        parts = self._selected_profile.get("parts", [])
        if idx < len(parts):
            parts.pop(idx)
        self._selected_profile["parts"] = parts
        self._update_preview()

    def _update_preview(self):
        if not self._selected_profile:
            return
        from ui.part_editor import part_to_display
        parts = self._selected_profile.get("parts", [])
        preview = "".join(
            part.get("value", "{" + part.get("type", "?") + "}")
            if part.get("type") == "text"
            else "{" + part_to_display(part) + "}"
            for part in parts
        )
        self.preview_label.setText(f"<b>{preview}.pdf</b>")

    def _add_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name.strip():
            import uuid
            profiles = config_manager.load_naming_profiles()
            new_profile = {
                "id": str(uuid.uuid4())[:8],
                "name": name.strip(),
                "date_format": "yyyy-mm-dd",
                "parts": [
                    {"type": "unit"},
                    {"type": "text", "value": " "},
                    {"type": "form_name"},
                    {"type": "text", "value": " "},
                    {"type": "date", "source": "today"}
                ]
            }
            profiles.append(new_profile)
            config_manager.save_naming_profiles(profiles)
            self._load_profiles()
            self.profile_list.setCurrentRow(len(profiles) - 1)

    def _save_profile(self):
        if not self._selected_profile:
            return
        # Sync drag-drop order back to parts (using internal list order)
        # Since drag-drop moves items in QListWidget but not our list, we'd need
        # to track order properly. For now, save current _selected_profile parts as-is.
        self._selected_profile["name"] = self.profile_name_input.text().strip()
        self._selected_profile["date_format"] = self.date_format_input.text().strip()

        profiles = config_manager.load_naming_profiles()
        for i, p in enumerate(profiles):
            if p["id"] == self._selected_profile.get("id"):
                profiles[i] = self._selected_profile
                break
        config_manager.save_naming_profiles(profiles)
        self._load_profiles()
        QMessageBox.information(self, "Saved", "Naming profile saved.")

    def _delete_profile(self):
        if not self._selected_profile:
            return
        reply = QMessageBox.question(self, "Delete Profile",
                                     f"Delete '{self._selected_profile['name']}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            profiles = config_manager.load_naming_profiles()
            profiles = [p for p in profiles if p["id"] != self._selected_profile["id"]]
            config_manager.save_naming_profiles(profiles)
            self._selected_profile = None
            self.editor_group.setEnabled(False)
            self._load_profiles()
