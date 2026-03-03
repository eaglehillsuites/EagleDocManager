"""
Form Filler Window - Main window for the Form Filler feature.
Orchestrates the full batch workflow:
  1. Batch settings popup
  2. CSV loading and per-form processing
  3. Batch review + lease type selection
  4. Renewal details (if Fixed-Term units exist)
  5. Save all to Waiting for Signature
"""

from __future__ import annotations
import os
import shutil
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QLineEdit, QGroupBox, QFormLayout,
    QCheckBox, QMessageBox, QProgressDialog, QFrame, QSplitter,
    QScrollArea, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

import config_manager
from form_filler import tracker
from form_filler.pdf_filler import (
    fill_pdf, build_increase_fields, build_renewal_fields,
    has_blank_required_fields, get_blank_fields,
    RENEWAL_INTENTIONALLY_BLANK, INCREASE_INTENTIONALLY_BLANK
)
from form_filler.csv_reader import read_csv, get_unit_id, has_blank_csv_fields
from form_filler.date_utils import ordinal_date_str, default_due_date

from ui.form_filler.batch_settings_dialog import BatchSettingsDialog
from ui.form_filler.form_review_dialog import FormReviewDialog
from ui.form_filler.batch_review_dialog import BatchReviewDialog
from ui.form_filler.renewal_details_dialog import RenewalDetailsDialog


def _btn(text: str, color: str = "#2c7be5") -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setStyleSheet(f"""
        QPushButton {{
            background-color: {color}; color: white;
            border-radius: 4px; font-weight: bold; padding: 0 14px;
        }}
        QPushButton:hover {{ background-color: {color}dd; }}
        QPushButton:disabled {{ background-color: #adb5bd; }}
    """)
    return b


class FormFillerWindow(QMainWindow):

    # Signal sent to dashboard when a batch is completed
    batch_completed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Form Filler — Eagle Doc Manager")
        self.setMinimumSize(900, 650)

        self._cfg = config_manager.load_config()
        self._increase_template = self._cfg.get(
            "increase_template", str(Path(__file__).parent.parent.parent /
                                     "config" / "Rental_Increase_Form_2026.pdf")
        )
        self._renewal_template = self._cfg.get(
            "renewal_template", str(Path(__file__).parent.parent.parent /
                                    "config" / "Fixed-Term_Extension_Form.pdf")
        )
        self._output_base = self._cfg.get(
            "form_filler_output",
            r"C:\Users\eagle\OneDrive\Desktop\To Be Processed"
        )
        self._flatten = self._cfg.get("form_filler_flatten", False)

        # State for current batch
        self._batch_settings: dict | None = None
        self._current_csv: str | None = None
        self._current_rows: list[dict] = []
        self._batch_records: list[dict] = []  # tracker records for this batch

        self._build_ui()
        self._refresh_status()

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Settings bar ──────────────────────────────────────
        settings_group = QGroupBox("Form Filler Settings")
        sg_layout = QFormLayout(settings_group)

        # Output folder
        out_row = QHBoxLayout()
        self._output_input = QLineEdit(self._output_base)
        self._output_input.textChanged.connect(self._on_output_changed)
        out_browse = QPushButton("Browse…")
        out_browse.setFixedHeight(28)
        out_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self._output_input)
        out_row.addWidget(out_browse)
        sg_layout.addRow("Output Folder:", out_row)

        # Increase template
        inc_row = QHBoxLayout()
        self._inc_template_input = QLineEdit(self._increase_template)
        self._inc_template_input.textChanged.connect(
            lambda t: setattr(self, "_increase_template", t))
        inc_browse = QPushButton("Browse…")
        inc_browse.setFixedHeight(28)
        inc_browse.clicked.connect(lambda: self._browse_template("increase"))
        inc_row.addWidget(self._inc_template_input)
        inc_row.addWidget(inc_browse)
        sg_layout.addRow("Increase Template:", inc_row)

        # Renewal template
        ren_row = QHBoxLayout()
        self._ren_template_input = QLineEdit(self._renewal_template)
        self._ren_template_input.textChanged.connect(
            lambda t: setattr(self, "_renewal_template", t))
        ren_browse = QPushButton("Browse…")
        ren_browse.setFixedHeight(28)
        ren_browse.clicked.connect(lambda: self._browse_template("renewal"))
        ren_row.addWidget(self._ren_template_input)
        ren_row.addWidget(ren_browse)
        sg_layout.addRow("Renewal Template:", ren_row)

        # Flatten toggle
        self._flatten_check = QCheckBox("Flatten filled PDFs (bakes fields permanently)")
        self._flatten_check.setChecked(self._flatten)
        self._flatten_check.toggled.connect(self._on_flatten_toggled)
        sg_layout.addRow("", self._flatten_check)

        # CSV file selector
        csv_row = QHBoxLayout()
        self._csv_path_input = QLineEdit()
        self._csv_path_input.setPlaceholderText("No CSV loaded")
        self._csv_path_input.setReadOnly(True)
        self._csv_path_input.setStyleSheet("background: #e9ecef; color: #495057;")
        csv_load_btn = QPushButton("Load CSV…")
        csv_load_btn.setFixedHeight(28)
        csv_load_btn.clicked.connect(self._load_csv)
        csv_row.addWidget(self._csv_path_input)
        csv_row.addWidget(csv_load_btn)
        sg_layout.addRow("CSV File:", csv_row)

        root.addWidget(settings_group)

        # ── Action bar ────────────────────────────────────────
        action_layout = QHBoxLayout()

        self._begin_btn = _btn("Begin Batch")
        self._begin_btn.setEnabled(False)
        self._begin_btn.clicked.connect(self._start_batch)
        action_layout.addWidget(self._begin_btn)
        action_layout.addStretch()

        root.addLayout(action_layout)

        # ── Status / current batch ────────────────────────────
        self._status_label = QLabel("No batch in progress.")
        self._status_label.setStyleSheet("color: #555; font-style: italic;")
        root.addWidget(self._status_label)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    # ── Settings handlers ─────────────────────────────────────

    def _on_output_changed(self, text: str):
        self._output_base = text
        self._save_settings()

    def _on_flatten_toggled(self, checked: bool):
        self._flatten = checked
        self._save_settings()

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder",
                                                  self._output_base)
        if folder:
            self._output_base = folder
            self._output_input.setText(folder)
            self._save_settings()

    def _browse_template(self, which: str):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF Template",
                                              "", "PDF Files (*.pdf)")
        if path:
            if which == "increase":
                self._increase_template = path
                self._inc_template_input.setText(path)
            else:
                self._renewal_template = path
                self._ren_template_input.setText(path)
            self._save_settings()

    def _save_settings(self):
        cfg = config_manager.load_config()
        cfg["form_filler_output"] = self._output_base
        cfg["increase_template"] = self._increase_template
        cfg["renewal_template"] = self._renewal_template
        cfg["form_filler_flatten"] = self._flatten
        config_manager.save_config(cfg)

    # ── Batch workflow ────────────────────────────────────────

    def _load_csv(self):
        """Load and validate a CSV file — separate from starting the batch."""
        csv_path, _ = QFileDialog.getOpenFileName(
            self, "Select Tenant CSV", "", "CSV Files (*.csv)"
        )
        if not csv_path:
            return
        try:
            rows = read_csv(csv_path)
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Could not read CSV:\n{e}")
            return
        if not rows:
            QMessageBox.information(self, "Empty CSV",
                                    "No data rows found in the selected CSV file.")
            return

        self._current_csv = csv_path
        self._current_rows = rows
        self._csv_path_input.setText(csv_path)
        self._csv_path_input.setStyleSheet("background: #e9ecef; color: #212529;")
        self._begin_btn.setEnabled(True)
        self._status_label.setText(
            f"CSV loaded: {len(rows)} row(s) ready.  Click \"Begin Batch\" to continue."
        )
        self._statusbar.showMessage(f"Loaded: {Path(csv_path).name}  ({len(rows)} rows)")

    def _start_batch(self):
        """Show batch settings popup then process the loaded CSV."""
        if not self._current_rows:
            QMessageBox.warning(self, "No CSV", "Please load a CSV file first.")
            return

        # Validate templates exist
        for label, path in [("Increase template", self._increase_template),
                             ("Renewal template", self._renewal_template)]:
            if not Path(path).exists():
                QMessageBox.warning(self, "Missing Template",
                                    f"{label} not found:\n{path}\n\n"
                                    "Please set the correct path in settings above.")
                return

        # Show batch settings dialog
        dlg = BatchSettingsDialog(self)
        if dlg.exec() != BatchSettingsDialog.Accepted:
            return

        self._batch_settings = dlg.get_result()
        self._batch_records = []
        self._process_csv_rows()

    def _process_csv_rows(self):
        """Step 1–3: Process each CSV row, show per-form review dialog."""
        waiting_dir = Path(self._output_base) / "Waiting for Signature"
        waiting_dir.mkdir(parents=True, exist_ok=True)

        today = date.today()
        settings = self._batch_settings

        for i, row in enumerate(self._current_rows):
            unit_id = get_unit_id(row)
            tenant = ", ".join(filter(None, [
                row.get("TenantName1", "").strip(),
                row.get("TenantName2", "").strip(),
                row.get("TenantName3", "").strip(),
            ]))

            self._statusbar.showMessage(
                f"Processing row {i+1} of {len(self._current_rows)}: {unit_id}"
            )

            # Build increase fields
            inc_fields = build_increase_fields(
                csv_row=row,
                delivery_date_str=settings["delivery_date"],
                due_date_str=settings["due_date"],
                increase_date_str=settings["increase_date"],
            )

            # Check for blanks (excluding intentional)
            force_edit = has_blank_required_fields(
                inc_fields, skip_fields=list(INCREASE_INTENTIONALLY_BLANK)
            )

            # Output path
            safe_unit = unit_id.replace("/", "-")
            inc_filename = f"{safe_unit} Rental Increase {today.strftime('%Y-%m')}.pdf"
            inc_path = str(waiting_dir / inc_filename)

            # Fill the PDF
            try:
                fill_pdf(self._increase_template, inc_path, inc_fields, self._flatten)
            except Exception as e:
                QMessageBox.critical(self, "Fill Error",
                                     f"Could not fill form for {unit_id}:\n{e}")
                continue

            # Show review dialog
            label = f"{unit_id} — Rental Increase"
            review = FormReviewDialog(
                pdf_path=inc_path,
                fields=inc_fields,
                form_label=label,
                force_edit=force_edit,
                parent=self
            )
            review.exec()

            awaiting = review.result_action == "edit_later"

            # If user edited fields, re-fill the PDF
            if review.result_fields != inc_fields:
                try:
                    fill_pdf(self._increase_template, inc_path,
                             review.result_fields, self._flatten)
                except Exception:
                    pass

            # Create tracker record
            rec = tracker.create_record(
                unit=unit_id,
                month=today.month,
                year=today.year,
                increase_path=inc_path,
                renewal_path=None,
                tenant_name=tenant,
                building_addr=row.get("BuildingAddr", ""),
            )
            if awaiting:
                tracker.update_record(unit_id, today.month, today.year,
                                      awaiting_review=True)
                rec["awaiting_review"] = True

            self._batch_records.append(rec)

        self._statusbar.showMessage("All forms generated. Opening batch review…")
        self._show_batch_review()

    def _show_batch_review(self):
        """Step 4: Show batch review checklist."""
        if not self._batch_records:
            return

        today = date.today()

        # Load previous year's lease types for pre-population
        prev_records = {
            r["unit"]: r for r in tracker.get_records_for_month(today.month, today.year - 1)
        }

        review_data = []
        for rec in self._batch_records:
            prev = prev_records.get(rec["unit"], {})
            review_data.append({
                "unit": rec["unit"],
                "tenant_name": rec.get("tenant_name", ""),
                "building_addr": rec.get("building_addr", ""),
                "awaiting_review": rec.get("awaiting_review", False),
                "previous_lease_type": prev.get("lease_type"),
            })

        while True:
            dlg = BatchReviewDialog(review_data, parent=self)
            dlg.edit_requested.connect(self._on_edit_from_review)

            if dlg.exec() != BatchReviewDialog.Accepted:
                # User cancelled — forms are already saved
                self._status_label.setText(
                    f"Batch saved ({len(self._batch_records)} forms). "
                    "Review cancelled — lease types not set."
                )
                return

            choices = dlg.get_result()

            # Update tracker with lease types and review flags
            for choice in choices:
                tracker.update_record(
                    choice["unit"], today.month, today.year,
                    lease_type=choice["lease_type"],
                    awaiting_review=choice["awaiting_review"],
                )

            fixed_units = [c["unit"] for c in choices if c["needs_renewal"]]

            if not fixed_units:
                # No renewals needed — done
                self._finish_batch(choices)
                return

            # Show renewal details
            result = self._show_renewal_details(fixed_units)
            if result == "back":
                # User went back — re-show batch review
                continue
            elif result == "done":
                self._finish_batch(choices)
                return

    def _on_edit_from_review(self, unit: str):
        """Called when Edit is clicked in batch review."""
        rec = next((r for r in self._batch_records if r["unit"] == unit), None)
        if not rec or not rec.get("increase_path"):
            return

        inc_path = rec["increase_path"]
        if not Path(inc_path).exists():
            QMessageBox.warning(self, "File Not Found",
                                f"Could not find:\n{inc_path}")
            return

        # Re-read current fields from the filled PDF
        from pypdf import PdfReader
        reader = PdfReader(inc_path)
        current_fields = {}
        pdf_fields = reader.get_fields() or {}
        for name, field in pdf_fields.items():
            current_fields[name] = field.get("/V", "") or ""

        review = FormReviewDialog(
            pdf_path=inc_path,
            fields=current_fields,
            form_label=f"{unit} — Edit",
            force_edit=True,
            parent=self
        )
        review.exec()

        if review.result_fields:
            try:
                fill_pdf(self._increase_template, inc_path,
                         review.result_fields, self._flatten)
            except Exception as e:
                QMessageBox.warning(self, "Save Error", str(e))

        today = date.today()
        tracker.update_record(unit, today.month, today.year,
                               awaiting_review=(review.result_action == "edit_later"))

    def _show_renewal_details(self, fixed_units: list[str]) -> str:
        """Shows renewal details dialog. Returns 'back', 'done', or 'cancel'."""
        dlg = RenewalDetailsDialog(self._batch_settings, fixed_units, parent=self)
        result = dlg.exec()

        if dlg.went_back():
            return "back"
        if result != RenewalDetailsDialog.Accepted:
            return "cancel"

        renewal_settings = dlg.get_result()
        self._generate_renewals(fixed_units, renewal_settings)
        return "done"

    def _generate_renewals(self, fixed_units: list[str], renewal_settings: dict):
        """Generate renewal PDFs for all Fixed-Term units."""
        today = date.today()
        waiting_dir = Path(self._output_base) / "Waiting for Signature"
        waiting_dir.mkdir(parents=True, exist_ok=True)

        for unit_id in fixed_units:
            # Find the CSV row for this unit
            row = next(
                (r for r in self._current_rows if get_unit_id(r) == unit_id),
                None
            )
            if not row:
                continue

            ren_fields = build_renewal_fields(
                csv_row=row,
                due_date_str=renewal_settings["due_date"],
                lease_start_str=renewal_settings["lease_start"],
                lease_end_str=renewal_settings["lease_end"],
                new_lease_end_str=renewal_settings["new_lease_end"],
                increase_date_str=renewal_settings["increase_date"],
            )

            safe_unit = unit_id.replace("/", "-")
            ren_filename = f"{safe_unit} Fixed-Term Extension {today.strftime('%Y-%m')}.pdf"
            ren_path = str(waiting_dir / ren_filename)

            try:
                fill_pdf(self._renewal_template, ren_path, ren_fields, self._flatten)
            except Exception as e:
                QMessageBox.warning(self, "Renewal Error",
                                    f"Could not fill renewal for {unit_id}:\n{e}")
                continue

            # Update tracker with renewal path
            tracker.update_record(unit_id, today.month, today.year,
                                   renewal_path=ren_path)

    def _finish_batch(self, choices: list[dict]):
        """Final step — update status and notify dashboard."""
        today = date.today()
        total = len(self._batch_records)
        renewals = sum(1 for c in choices if c.get("needs_renewal"))

        self._status_label.setText(
            f"✓ Batch complete — {total} increase form(s) generated"
            + (f", {renewals} with renewal forms" if renewals else "")
            + f"\nSaved to: {Path(self._output_base) / 'Waiting for Signature'}"
        )
        self._statusbar.showMessage("Batch complete.")
        self.batch_completed.emit()

        QMessageBox.information(
            self, "Batch Complete",
            f"{total} form(s) saved to 'Waiting for Signature'."
            + (f"\n{renewals} renewal form(s) also generated." if renewals else "")
        )

    def _refresh_status(self):
        today = date.today()
        metrics = tracker.get_metrics(today.month, today.year)
        if metrics["total"] > 0:
            self._status_label.setText(
                f"Current month: {metrics['total']} forms — "
                f"Entered: {metrics['entered']}  "
                f"Delivered: {metrics['delivered']}  "
                f"Signed: {metrics['signed']}  "
                f"Overdue: {metrics['overdue']}"
            )
