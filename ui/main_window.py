"""
Main Window - The primary application window with settings tabs and processing controls.
"""

import sys
import threading
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QStatusBar, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QIcon, QFont, QAction

import config_manager
from watcher import FolderWatcher
from processor.engine import DocumentProcessor, process_folder, ProcessingResult
from ui.settings_tabs.tabs import (
    GeneralTab, AutoScanTab, ManualScanTab, FormsTab, NamingConventionsTab
)
from ui.completion_dialog import CompletionDialog
from ui.duplicate_dialog import DuplicateDialog
from ui.date_popups import RenewalDateDialog, CustomDateDialog, FormTypeDialog
from ui.out_inspection_dialog import OutInspectionDialog


# ─────────────────────────────────────────
#  Background Worker
# ─────────────────────────────────────────

class ProcessWorker(QObject):
    """Runs document processing in a background thread."""
    progress = Signal(str)
    finished = Signal(list)  # List of result dicts
    need_form_type = Signal(object, str)  # image, filename -> blocks
    need_renewal_date = Signal(str)
    need_custom_date = Signal(str)
    duplicate_found = Signal(str, str, str)

    def __init__(self, folder: str, mode: int):
        super().__init__()
        self.folder = folder
        self.mode = mode
        self._form_type_result = None
        self._renewal_date_result = None
        self._custom_date_result = None
        self._duplicate_result = None
        self._waiting = threading.Event()

    def run(self):
        processor = DocumentProcessor(
            on_need_form_type=self._on_need_form_type,
            on_need_renewal_date=self._on_need_renewal_date,
            on_need_custom_date=self._on_need_custom_date,
            on_duplicate=self._on_duplicate,
            on_progress=lambda msg: self.progress.emit(msg)
        )
        results = process_folder(self.folder, self.mode, processor=processor)
        self.finished.emit([r.to_dict() for r in results])

    def _on_need_form_type(self, image, filename: str) -> str:
        self._waiting.clear()
        self.need_form_type.emit(image, filename)
        self._waiting.wait(timeout=120)
        return self._form_type_result or ""

    def _on_need_renewal_date(self, form_name: str) -> str:
        self._waiting.clear()
        self.need_renewal_date.emit(form_name)
        self._waiting.wait(timeout=120)
        return self._renewal_date_result or ""

    def _on_need_custom_date(self, form_name: str) -> str:
        self._waiting.clear()
        self.need_custom_date.emit(form_name)
        self._waiting.wait(timeout=120)
        return self._custom_date_result or ""

    def _on_duplicate(self, existing_path: str, incoming_path: str, filename: str) -> str:
        self._waiting.clear()
        self.duplicate_found.emit(existing_path, incoming_path, filename)
        self._waiting.wait(timeout=120)
        return self._duplicate_result or "skip"

    def resolve_form_type(self, value: str):
        self._form_type_result = value
        self._waiting.set()

    def resolve_renewal_date(self, value: str):
        self._renewal_date_result = value
        self._waiting.set()

    def resolve_custom_date(self, value: str):
        self._custom_date_result = value
        self._waiting.set()

    def resolve_duplicate(self, action: str):
        self._duplicate_result = action
        self._waiting.set()


# ─────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eagle Doc Manager")
        self.setMinimumSize(900, 650)

        self._watcher = None
        self._worker = None
        self._worker_thread = None

        self._build_ui()
        self._setup_watcher()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("background-color: #1a1a2e;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("🦅  Eagle Doc Manager")
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.status_indicator = QLabel("● Watcher: Stopped")
        self.status_indicator.setStyleSheet("color: #aaa; font-size: 12px;")
        header_layout.addWidget(self.status_indicator)

        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 10px 20px; font-size: 13px; }
            QTabBar::tab:selected { border-bottom: 3px solid #2c7be5; font-weight: bold; }
        """)

        self.general_tab = GeneralTab()
        self.auto_scan_tab = AutoScanTab()
        self.manual_scan_tab = ManualScanTab()
        self.forms_tab = FormsTab()
        self.naming_tab = NamingConventionsTab()

        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.auto_scan_tab, "Auto Scan")
        self.tabs.addTab(self.manual_scan_tab, "Manual Scan")
        self.tabs.addTab(self.forms_tab, "Forms")
        self.tabs.addTab(self.naming_tab, "Naming Conventions")

        main_layout.addWidget(self.tabs)

        # Connect signals
        self.auto_scan_tab.watcher_status_changed.connect(self._on_watcher_control)
        self.manual_scan_tab.process_folder_requested.connect(self._on_process_folder)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _setup_watcher(self):
        """Initialize and start the folder watcher."""
        cfg = config_manager.load_config()
        folders = cfg.get("watched_folders", [])
        exceptions = cfg.get("exceptions", [])
        mode = cfg.get("scan_mode", 1)

        self._watcher = FolderWatcher(
            on_new_file=lambda path: self._on_watcher_file(path, mode),
            exceptions=exceptions
        )
        self._watcher.set_folders(folders)

        if folders:
            self._watcher.start()
            self._update_watcher_indicator(True)
            self.auto_scan_tab.set_watcher_running(True)

    def _update_watcher_indicator(self, running: bool):
        if running:
            self.status_indicator.setText("● Watcher: Running")
            self.status_indicator.setStyleSheet("color: #5cb85c; font-size: 12px;")
        else:
            self.status_indicator.setText("● Watcher: Stopped")
            self.status_indicator.setStyleSheet("color: #aaa; font-size: 12px;")

    def _on_watcher_control(self, should_run: bool):
        if should_run:
            cfg = config_manager.load_config()
            self._watcher.set_folders(cfg.get("watched_folders", []))
            self._watcher.set_exceptions(cfg.get("exceptions", []))
            self._watcher.start()
            self._update_watcher_indicator(True)
        else:
            self._watcher.stop()
            self._update_watcher_indicator(False)

    def _on_watcher_file(self, path: str, mode: int):
        """Called by watcher thread when a new file is detected."""
        folder = str(Path(path).parent)
        # Use invokeMethod-style: run from main thread
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self, "_run_process_folder",
                                 Qt.QueuedConnection,
                                 path, folder, mode)

    @Slot(str, str, int)
    def _run_process_folder(self, triggered_file: str, folder: str, mode: int):
        self._on_process_folder(folder, mode)

    def _on_process_folder(self, folder: str, mode: int):
        """Start processing a folder in background."""
        if self._worker_thread and self._worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Processing is already in progress.")
            return

        self.status_bar.showMessage(f"Processing: {folder}...")
        self._worker_thread = QThread()
        self._worker = ProcessWorker(folder, mode)
        self._worker.moveToThread(self._worker_thread)

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_processing_finished)
        self._worker.need_form_type.connect(self._show_form_type_dialog)
        self._worker.need_renewal_date.connect(self._show_renewal_date_dialog)
        self._worker.need_custom_date.connect(self._show_custom_date_dialog)
        self._worker.duplicate_found.connect(self._show_duplicate_dialog)

        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    @Slot(str)
    def _on_progress(self, message: str):
        self.status_bar.showMessage(message)
        self.manual_scan_tab.append_log(message)

    @Slot(list)
    def _on_processing_finished(self, results: list):
        self.status_bar.showMessage("Processing complete.")
        self._worker_thread.quit()
        self._worker_thread.wait()

        # Check for out-inspection
        out_inspections = [r for r in results if r.get("form_type", "").lower() == "out-inspection"]
        for r in out_inspections:
            self._handle_out_inspection(r)

        # Show completion dialog
        if results:
            dialog = CompletionDialog(results, parent=self)
            dialog.exec()

    def _handle_out_inspection(self, result: dict):
        unit = result.get("unit", "")
        generated_path = result.get("generated_path", "")
        if not generated_path:
            return

        unit_folder = str(Path(generated_path).parent)
        dialog = OutInspectionDialog(unit=unit, unit_folder=unit_folder, parent=self)

        if dialog.exec():
            tenant_name = dialog.get_tenant_name()
            cfg = config_manager.load_config()
            prev_path = cfg.get("previous_tenants_path", "")

            if prev_path:
                from processor.mover import move_unit_folder_to_previous
                from processor.undo_manager import record_unit_folder_move
                try:
                    new_folder = move_unit_folder_to_previous(
                        unit_folder=unit_folder,
                        previous_tenants_root=prev_path,
                        tenant_name=tenant_name,
                        unit_id=unit
                    )
                    record_unit_folder_move(
                        source_filename=result.get("original_file", ""),
                        original_unit_folder=unit_folder,
                        new_unit_folder=new_folder
                    )
                    self.status_bar.showMessage(
                        f"Unit {unit} moved to Previous Tenants as '{tenant_name}'"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not move unit folder:\n{e}")
            else:
                QMessageBox.warning(self, "No Path",
                                    "Previous Tenants path not configured in General settings.")

    @Slot(object, str)
    def _show_form_type_dialog(self, image, filename: str):
        dialog = FormTypeDialog(preview_image=image, filename=filename, parent=self)
        if dialog.exec():
            self._worker.resolve_form_type(dialog.get_form_type())
        else:
            self._worker.resolve_form_type("")

    @Slot(str)
    def _show_renewal_date_dialog(self, form_name: str):
        # Get the date format from the form's naming profile
        cfg_forms = config_manager.load_forms()
        date_format = "mmmYYYY"
        for f in cfg_forms:
            if f["name"] == form_name:
                profile = config_manager.get_naming_profile(f.get("naming_profile_id", ""))
                if profile:
                    date_format = profile.get("date_format", "mmmYYYY")
                break

        dialog = RenewalDateDialog(date_format=date_format, form_name=form_name, parent=self)
        if dialog.exec():
            self._worker.resolve_renewal_date(dialog.get_value())
        else:
            self._worker.resolve_renewal_date("")

    @Slot(str)
    def _show_custom_date_dialog(self, form_name: str):
        dialog = CustomDateDialog(
            prompt="Enter the custom date or text for this file:",
            form_name=form_name,
            parent=self
        )
        if dialog.exec():
            self._worker.resolve_custom_date(dialog.get_value())
        else:
            self._worker.resolve_custom_date("")

    @Slot(str, str, str)
    def _show_duplicate_dialog(self, existing_path: str, incoming_path: str, filename: str):
        dialog = DuplicateDialog(
            existing_path=existing_path,
            incoming_path=incoming_path,
            filename=filename,
            parent=self
        )
        dialog.exec()
        self._worker.resolve_duplicate(dialog.get_action())

    def closeEvent(self, event):
        if self._watcher:
            self._watcher.stop()
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        event.accept()
