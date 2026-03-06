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
from ui.pick_destination_dialog import PickDestinationDialog


# ─────────────────────────────────────────
#  Background Worker
# ─────────────────────────────────────────

class ProcessWorker(QObject):
    """Runs document processing in a background thread."""
    progress = Signal(str)
    finished = Signal(list)  # List of result dicts
    need_form_type = Signal(object, str, str)  # image, filename, ocr_text
    need_renewal_date = Signal(str, object)  # form_name, preview_image
    need_custom_date = Signal(str)
    duplicate_found = Signal(str, str, str)
    need_unknown_qr = Signal(str, str)   # qr_text, filename
    need_preconfirm = Signal(list)       # list of pending result dicts
    need_destination = Signal(str, str, object, str)  # filename, reason, preview, proposed_fname

    def __init__(self, folder: str, mode: int):
        super().__init__()
        self.folder = folder
        self.mode = mode
        self._form_type_result = None
        self._renewal_date_result = None
        self._custom_date_result = None
        self._duplicate_result = None
        self._unknown_qr_result = None
        self._destination_result = None
        self._last_preview_img = None
        self._waiting = threading.Event()

    def run(self):
        try:
            processor = DocumentProcessor(
                on_need_form_type=self._on_need_form_type,
                on_need_renewal_date=self._on_need_renewal_date,
                on_need_custom_date=self._on_need_custom_date,
                on_duplicate=self._on_duplicate,
                on_unknown_qr=self._on_need_unknown_qr,
                on_need_destination=self._on_need_destination,
                on_progress=lambda msg: self.progress.emit(msg)
            )
            results = process_folder(self.folder, self.mode, processor=processor)
            self.finished.emit([r.to_dict() for r in results])
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.progress.emit(f"ERROR during processing: {e}")
            self.progress.emit(tb)
            error_result = {
                "original_file": self.folder,
                "generated_file": "", "generated_path": "",
                "unit": "", "form_type": "",
                "scan_mode": self.mode,
                "action": "Error",
                "notes": f"Unexpected error: {e}",
                "source_folder": self.folder,
            }
            self.finished.emit([error_result])

    def _on_need_form_type(self, image, filename: str, ocr_text: str = "") -> str:
        self._waiting.clear()
        self.need_form_type.emit(image, filename, ocr_text)
        self._waiting.wait(timeout=120)
        return self._form_type_result or ""

    def _on_need_renewal_date(self, form_name: str, preview_img=None) -> str:
        self._last_preview_img = preview_img
        self._waiting.clear()
        self.need_renewal_date.emit(form_name, preview_img)
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

    def _on_need_unknown_qr(self, qr_text: str, filename: str):
        self._waiting.clear()
        self.need_unknown_qr.emit(qr_text, filename)
        self._waiting.wait(timeout=120)
        return self._unknown_qr_result

    def resolve_unknown_qr(self, result):
        self._unknown_qr_result = result
        self._waiting.set()

    def _on_need_destination(self, filename: str, reason: str,
                              preview_image, proposed_filename: str) -> dict | None:
        self._destination_result = None
        self._waiting.clear()
        self.need_destination.emit(filename, reason, preview_image, proposed_filename)
        self._waiting.wait(timeout=300)
        return self._destination_result

    def resolve_destination(self, result):
        self._destination_result = result
        self._waiting.set()

    def unblock(self):
        """Safety valve: unblock a stuck wait (called on error or close)."""
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
        if self._worker_thread is not None and self._worker_thread.isRunning():
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
        self._worker.need_unknown_qr.connect(self._show_unknown_qr_dialog)
        self._worker.need_destination.connect(self._show_pick_destination_dialog)

        self._worker_thread.started.connect(self._worker.run)
        self._worker_thread.start()

    @Slot(str)
    def _on_progress(self, message: str):
        self.status_bar.showMessage(message)
        self.manual_scan_tab.append_log(message)

    @Slot(list)
    def _on_processing_finished(self, results: list):
        self.status_bar.showMessage("Processing complete.")

        # Cleanly stop and discard the thread/worker so a new batch can start
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(5000)
        self._worker_thread = None
        self._worker = None

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
                    # Record before moving (while files still exist for date extraction)
                    from processor.previous_tenant_recorder import record_previous_tenant
                    record_previous_tenant(
                        tenant_name=tenant_name,
                        unit_id=unit,
                        unit_folder=unit_folder,
                        new_previous_folder=""   # filled in after move
                    )
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
                    # Update the CSV record with the actual destination
                    from processor.previous_tenant_recorder import record_previous_tenant
                    from pathlib import Path as _Path
                    import csv as _csv, config_manager as _cm
                    csv_path = _cm.get_previous_tenant_csv()
                    if _Path(csv_path).exists():
                        import csv as _csv2
                        rows = []
                        with open(csv_path, newline="", encoding="utf-8") as _f:
                            rows = list(_csv2.DictReader(_f))
                        if rows:
                            rows[-1]["previous_folder"] = new_folder
                            with open(csv_path, "w", newline="", encoding="utf-8") as _f:
                                w = _csv2.DictWriter(_f, fieldnames=rows[0].keys())
                                w.writeheader()
                                w.writerows(rows)
                    self.status_bar.showMessage(
                        f"Unit {unit} moved to Previous Tenants as '{tenant_name}'"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not move unit folder:\n{e}")
            else:
                QMessageBox.warning(self, "No Path",
                                    "Previous Tenants path not configured in General settings.")

    @Slot(object, str, str)
    def _show_form_type_dialog(self, image, filename: str, ocr_text: str = ""):
        if self._worker:
            self._worker._last_preview_img = image
        dialog = FormTypeDialog(preview_image=image, filename=filename,
                                ocr_text=ocr_text, parent=self)
        if dialog.exec():
            form_type = dialog.get_form_type()
            self._worker.resolve_form_type(form_type)
        else:
            self._worker.resolve_form_type("")

    @Slot(object, str)
    def _show_unknown_qr_dialog(self, qr_text: str, filename: str):
        """Handle unknown QR codes — connect to existing form or create new route."""
        from ui.unknown_qr_dialog import UnknownQRDialog
        dialog = UnknownQRDialog(qr_text=qr_text, filename=filename, parent=self)
        if dialog.exec():
            result = dialog.get_result()
            self._worker.resolve_unknown_qr(result)
        else:
            self._worker.resolve_unknown_qr(None)

    @Slot(str, object)
    def _show_renewal_date_dialog(self, form_name: str, preview_img=None):
        cfg_forms = config_manager.load_forms()
        date_format = "mmmYYYY"
        for f in cfg_forms:
            if f["name"] == form_name:
                profile = config_manager.get_naming_profile(f.get("naming_profile_id", ""))
                if profile:
                    date_format = profile.get("date_format", "mmmYYYY")
                break
        dialog = RenewalDateDialog(
            date_format=date_format,
            form_name=form_name,
            preview_image=preview_img,
            parent=self
        )
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

    @Slot(str, str, object, str)
    def _show_pick_destination_dialog(self, filename: str, reason: str,
                                      preview_image, proposed_filename: str):
        dialog = PickDestinationDialog(
            filename=filename,
            reason=reason,
            preview_image=preview_image,
            proposed_filename=proposed_filename,
            parent=self
        )
        if dialog.exec():
            self._worker.resolve_destination(dialog.get_result())
        else:
            self._worker.resolve_destination(None)

    def closeEvent(self, event):
        if self._watcher:
            self._watcher.stop()
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        event.accept()
