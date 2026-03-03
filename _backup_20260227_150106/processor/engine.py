"""
Processing Engine - Orchestrates the full document processing pipeline.
"""

import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

import config_manager
from processor.barcode_reader import scan_page_for_codes, parse_qr_unit, is_separator_page
from processor.splitter import split_pdf, extract_segment_to_pdf, archive_original, DocumentSegment
from processor.naming_engine import build_filename, needs_renewal_date, needs_custom_date, determine_destination_folder
from processor.duplicate_checker import check_duplicate, generate_numbered_names, DuplicateCheckResult
from processor.mover import move_file, move_unit_folder_to_previous
from processor.audit_logger import log_entry
from processor.undo_manager import record_batch, record_unit_folder_move
from processor.hooks import hooks


class ProcessingResult:
    """Result object for a single processed document segment."""

    def __init__(self):
        self.success = False
        self.original_file = ""
        self.source_folder = ""
        self.generated_file = ""
        self.generated_path = ""
        self.unit = ""
        self.form_type = ""
        self.scan_mode = 1
        self.action = ""
        self.notes = ""
        self.skipped = False
        self.needs_manual_form_type = False
        self.needs_renewal_date = False
        self.needs_custom_date = False
        self.duplicate_result: Optional[DuplicateCheckResult] = None

    def to_dict(self):
        return {
            "original_file": self.original_file,
            "generated_file": self.generated_file,
            "generated_path": self.generated_path,
            "unit": self.unit,
            "form_type": self.form_type,
            "scan_mode": self.scan_mode,
            "action": self.action,
            "notes": self.notes,
            "source_folder": self.source_folder
        }


class DocumentProcessor:
    """
    Main processing class. Handles the full pipeline for a single PDF file.
    
    Callbacks (set from UI):
    - on_need_form_type(page_preview_image) -> str : UI asks user for form type
    - on_need_renewal_date(form_name) -> str : returns formatted date string
    - on_need_custom_date(form_name) -> str : returns custom text
    - on_duplicate(existing_path, new_temp_path, filename) -> str : "replace"|"skip"|"number"
    - on_progress(message: str)
    """

    def __init__(self,
                 on_need_form_type: Optional[Callable] = None,
                 on_need_renewal_date: Optional[Callable] = None,
                 on_need_custom_date: Optional[Callable] = None,
                 on_duplicate: Optional[Callable] = None,
                 on_progress: Optional[Callable] = None):

        self.on_need_form_type = on_need_form_type
        self.on_need_renewal_date = on_need_renewal_date
        self.on_need_custom_date = on_need_custom_date
        self.on_duplicate = on_duplicate
        self.on_progress = on_progress

    def _log(self, msg: str):
        if self.on_progress:
            self.on_progress(msg)
        print(f"[DocProcessor] {msg}")

    def process_file(self, pdf_path: str, scan_mode: int) -> list[ProcessingResult]:
        """
        Process a single PDF file. Returns list of ProcessingResult objects
        (one per document segment found).
        """
        config = config_manager.load_config()
        exceptions = config.get("exceptions", [])
        filename = Path(pdf_path).name

        # Check exceptions
        for exc in exceptions:
            if exc.lower() in filename.lower():
                self._log(f"Skipping '{filename}' (matches exception: '{exc}')")
                r = ProcessingResult()
                r.skipped = True
                r.original_file = filename
                r.notes = f"Skipped: exception match '{exc}'"
                return [r]

        self._log(f"Processing: {filename}")

        source_folder = str(Path(pdf_path).parent)
        results = []

        # Step 1: Split PDF into segments
        try:
            segments = split_pdf(pdf_path, scan_mode)
        except Exception as e:
            self._log(f"Error splitting PDF: {e}")
            r = ProcessingResult()
            r.original_file = filename
            r.source_folder = source_folder
            r.notes = f"Error: {e}"
            return [r]

        self._log(f"Found {len(segments)} document segment(s)")

        generated_files_for_undo = []
        archive_path = None
        out_inspection_triggered = False
        out_inspection_unit = None
        out_inspection_unit_folder = None

        # Create temp directory for segment extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, segment in enumerate(segments):
                result = self._process_segment(
                    segment=segment,
                    pdf_path=pdf_path,
                    source_folder=source_folder,
                    scan_mode=scan_mode,
                    config=config,
                    segment_index=i,
                    total_segments=len(segments),
                    tmpdir=tmpdir
                )
                results.append(result)

                if result.success and not result.skipped:
                    generated_files_for_undo.append({
                        "path": result.generated_path,
                        "filename": result.generated_file
                    })

                    # Check for out-inspection trigger
                    forms = config_manager.load_forms()
                    for f in forms:
                        if f.get("name", "").lower() == result.form_type.lower():
                            if f.get("id") == "inspection_out":
                                out_inspection_triggered = True
                                out_inspection_unit = result.unit
                                out_inspection_unit_folder = str(
                                    Path(result.generated_path).parent
                                )
                            break

            # Step 2: Archive original (for multi-page splits, or always)
            if len(segments) > 1 or scan_mode in (2, 3):
                try:
                    archive_path = archive_original(pdf_path)
                    self._log(f"Archived original: {Path(archive_path).name}")
                    # Delete original after archiving
                    if Path(pdf_path).exists():
                        Path(pdf_path).unlink()
                except Exception as e:
                    self._log(f"Archive error: {e}")

        # Step 3: Record undo entry
        if generated_files_for_undo:
            record_batch(
                source_folder=source_folder,
                source_filename=filename,
                generated_files=generated_files_for_undo,
                archive_path=archive_path
            )

        # Step 4: Handle out-inspection trigger (after all files are processed)
        if out_inspection_triggered and out_inspection_unit:
            self._handle_out_inspection(
                unit=out_inspection_unit,
                unit_folder=out_inspection_unit_folder,
                source_filename=filename,
                config=config
            )

        # Step 5: Write audit log
        for r in results:
            if not r.skipped:
                log_entry(
                    source_folder=source_folder,
                    original_file=r.original_file,
                    generated_file=r.generated_file,
                    unit=r.unit,
                    form_type=r.form_type,
                    scan_mode=scan_mode,
                    action=r.action,
                    notes=r.notes
                )

        # Fire batch hook
        hooks.fire("after_batch_complete", [r.to_dict() for r in results])

        return results

    def _process_segment(self, segment: DocumentSegment, pdf_path: str,
                          source_folder: str, scan_mode: int, config: dict,
                          segment_index: int, total_segments: int, tmpdir: str
                          ) -> ProcessingResult:
        result = ProcessingResult()
        result.original_file = Path(pdf_path).name
        result.source_folder = source_folder
        result.scan_mode = scan_mode

        # Get unit from QR
        unit = segment.qr_unit or ""
        result.unit = unit

        # Get form type from Data Matrix
        dm_value = segment.datamatrix_value or ""
        form = config_manager.get_form_by_datamatrix(dm_value) if dm_value else None
        form_name = form["name"] if form else None

        # If no form type detected, ask user
        if not form_name:
            if self.on_need_form_type:
                # Extract first page image for preview
                from pdf2image import convert_from_path
                try:
                    pages = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
                    preview_img = pages[0] if pages else None
                except Exception:
                    preview_img = None

                self._log("No form type detected - asking user...")
                user_form_type = self.on_need_form_type(preview_img, Path(pdf_path).name)
                if user_form_type:
                    form_name = user_form_type
                    # Find matching form object if possible
                    forms = config_manager.load_forms()
                    for f in forms:
                        if f["name"].lower() == user_form_type.lower():
                            form = f
                            break
                else:
                    result.notes = "No form type provided by user"
                    result.action = "Skipped"
                    result.skipped = True
                    return result
            else:
                form_name = "Unknown"

        result.form_type = form_name

        # Build date values
        date_values = {"today": datetime.now().strftime("%Y-%m-%d")}
        profile = None
        if form:
            profile = config_manager.get_naming_profile(form.get("naming_profile_id", ""))

        if profile:
            if needs_renewal_date(profile) and self.on_need_renewal_date:
                renewal_date = self.on_need_renewal_date(form_name)
                date_values["renewal"] = renewal_date or ""

            if needs_custom_date(profile) and self.on_need_custom_date:
                custom_date = self.on_need_custom_date(form_name)
                date_values["custom"] = custom_date or ""

        # Build filename
        if form:
            proposed_filename = build_filename(form, unit, date_values)
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            safe_unit = unit or "NOUNIT"
            safe_form = form_name.replace(" ", "_")
            proposed_filename = f"{safe_unit} {safe_form} {today}.pdf"

        # Determine destination
        dest_folder = determine_destination_folder(config, unit)
        if not dest_folder:
            result.notes = "No tenant root configured"
            result.action = "Error"
            return result

        # Duplicate check
        dup_result = check_duplicate(
            dest_folder=dest_folder,
            proposed_filename=proposed_filename,
            unit=unit,
            form_type=form_name,
            date_str=date_values.get("today", "")
        )

        final_filename = proposed_filename
        if dup_result.is_duplicate:
            self._log(f"Duplicate detected: {dup_result.reason}")

            if self.on_duplicate:
                # Extract segment to temp file for preview
                temp_path = os.path.join(tmpdir, f"incoming_{segment_index}.pdf")
                extract_segment_to_pdf(pdf_path, segment, temp_path)

                action = self.on_duplicate(
                    existing_path=dup_result.existing_path,
                    incoming_path=temp_path,
                    filename=proposed_filename
                )
                if action == "skip":
                    result.action = "Skipped (duplicate)"
                    result.skipped = True
                    return result
                elif action == "replace":
                    import os
                    if Path(dup_result.existing_path).exists():
                        Path(dup_result.existing_path).unlink()
                    final_filename = proposed_filename
                elif action == "number":
                    name1, name2 = generate_numbered_names(proposed_filename)
                    # Rename existing to (1)
                    existing_p = Path(dup_result.existing_path)
                    if existing_p.exists():
                        existing_p.rename(existing_p.parent / name1)
                    final_filename = name2
            else:
                # Default: number them
                name1, name2 = generate_numbered_names(proposed_filename)
                existing_p = Path(dup_result.existing_path)
                if existing_p.exists():
                    existing_p.rename(existing_p.parent / name1)
                final_filename = name2

        result.duplicate_result = dup_result

        # Extract segment to temp file
        temp_path = os.path.join(tmpdir, f"segment_{segment_index}.pdf")
        extract_segment_to_pdf(pdf_path, segment, temp_path)

        # Move to destination
        try:
            final_path = move_file(temp_path, dest_folder, final_filename)
            result.generated_file = final_filename
            result.generated_path = final_path
            result.action = "Moved"
            result.success = True
            self._log(f"✓ {final_filename} → {dest_folder}")

            hooks.fire("after_move", result.to_dict())

        except Exception as e:
            result.notes = f"Move error: {e}"
            result.action = "Error"
            self._log(f"Error moving file: {e}")

        return result

    def _handle_out_inspection(self, unit: str, unit_folder: str,
                                source_filename: str, config: dict):
        """Handle post-processing when an Out-Inspection is detected."""
        prev_path = config.get("previous_tenants_path", "")
        if not prev_path:
            self._log("Out-Inspection detected but no Previous Tenants path configured")
            return

        self._log(f"Out-Inspection detected for unit {unit}")
        hooks.fire("on_out_inspection", unit, unit_folder)


def process_folder(folder_path: str, scan_mode: int,
                   processor: Optional[DocumentProcessor] = None,
                   on_progress: Optional[Callable] = None) -> list[ProcessingResult]:
    """
    Process all PDFs in a folder. Returns all results.
    """
    if processor is None:
        processor = DocumentProcessor(on_progress=on_progress)

    folder = Path(folder_path)
    if not folder.exists():
        return []

    pdf_files = list(folder.glob("*.pdf"))
    # Exclude audit log PDF artifacts and archive subfolder
    pdf_files = [f for f in pdf_files if "Archive" not in str(f)]

    all_results = []
    for pdf_file in pdf_files:
        results = processor.process_file(str(pdf_file), scan_mode)
        all_results.extend(results)

    return all_results
