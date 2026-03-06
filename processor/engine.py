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
from processor.barcode_reader import scan_page_for_codes, parse_qr_unit, is_separator_page, is_building_level_unit
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
                 on_unknown_qr: Optional[Callable] = None,
                 on_preconfirm: Optional[Callable] = None,
                 on_need_destination: Optional[Callable] = None,
                 on_progress: Optional[Callable] = None):

        self.on_need_form_type = on_need_form_type
        self.on_need_renewal_date = on_need_renewal_date
        self.on_need_custom_date = on_need_custom_date
        self.on_duplicate = on_duplicate
        self.on_unknown_qr = on_unknown_qr
        self.on_preconfirm = on_preconfirm
        self.on_need_destination = on_need_destination
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
                try:
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
                except Exception as _seg_err:
                    import traceback as _tb
                    self._log(f"Error processing segment {i+1}: {_seg_err}")
                    self._log(_tb.format_exc())
                    result = ProcessingResult()
                    result.original_file = Path(pdf_path).name
                    result.source_folder = source_folder
                    result.action = "Error"
                    result.notes = f"Segment error: {_seg_err}"
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
        preview_img = None           # may be set early and reused
        final_filename_override = None   # set by on_need_destination if user edits filename

        # Get unit from QR
        # segment.qr_unit is pre-parsed; segment.raw_qr holds original string
        # segment.qr_diagnosis holds why detection failed (empty if succeeded)
        unit = segment.qr_unit or ""
        qr_diagnosis = getattr(segment, "qr_diagnosis", "")

        if not unit and getattr(segment, "raw_qr", None):
            # Non-standard QR format — check persistent routes first
            raw = segment.raw_qr
            cfg_routes = config.get("qr_routes", {})
            if raw in cfg_routes:
                unit = raw
            elif self.on_unknown_qr:
                self._log(f"Unknown QR code: {raw}")
                resolution = self.on_unknown_qr(raw, Path(pdf_path).name)
                if resolution:
                    if resolution.get("action") == "route":
                        import config_manager as _cm2
                        _cm2.save_qr_route(raw, resolution["folder"])
                        config = config_manager.load_config()
                        unit = raw
                    elif resolution.get("action") == "form":
                        form_override = resolution.get("form")

        # QR fallback: try to read unit/building from the form body via OCR
        if not unit:
            if qr_diagnosis:
                self._log(f"QR detection failed: {qr_diagnosis}")
            self._log("Attempting to read unit number from form text via OCR...")
            if preview_img is None:
                try:
                    from pdf2image import convert_from_path as _c2p
                    _pages = _c2p(pdf_path, dpi=200, first_page=1, last_page=1)
                    preview_img = _pages[0] if _pages else None
                except Exception:
                    pass
            if preview_img is not None:
                from processor.ocr_reader import ocr_available, extract_unit_from_ocr
                if ocr_available():
                    ocr_unit, ocr_note = extract_unit_from_ocr(preview_img)
                    if ocr_unit:
                        unit = ocr_unit
                        self._log(f"OCR found unit from form text: {unit} ({ocr_note})")
                    else:
                        self._log(f"OCR unit extraction: {ocr_note}")
                else:
                    self._log("Tesseract not available — cannot read unit from form text")

        result.unit = unit

        # Get form type from Data Matrix
        dm_value = segment.datamatrix_value or ""
        form = config_manager.get_form_by_datamatrix(dm_value) if dm_value else None
        form_name = form["name"] if form else None

        # Step 2 fallback: OCR title recognition
        if not form_name:
            if preview_img is None:
                from pdf2image import convert_from_path
                try:
                    pages = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
                    preview_img = pages[0] if pages else None
                except Exception:
                    pass  # leave preview_img as None; OCR will be skipped below

            if preview_img is not None:
                from processor.ocr_reader import match_form_by_ocr, ocr_available
                if ocr_available():
                    self._log("No Data Matrix found — trying OCR title recognition...")
                    ocr_form, ocr_text = match_form_by_ocr(preview_img)
                    if ocr_form:
                        form = ocr_form
                        form_name = ocr_form["name"]
                        self._log(f"OCR identified form type: {form_name}")
                    else:
                        self._log("OCR could not identify form type")
                else:
                    self._log("OCR not available (Tesseract not installed) — skipping OCR step")

        # Step 3 fallback: ask user
        if not form_name:
            if self.on_need_form_type:
                # Reuse preview_img already extracted above if available
                if preview_img is None:
                    from pdf2image import convert_from_path
                    try:
                        pages = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
                        preview_img = pages[0] if pages else None
                    except Exception:
                        pass

                self._log("Asking user for form type...")
                # Pass OCR text so UI can suggest keywords automatically
                _ocr_text_for_dialog = ""
                if preview_img is not None:
                    try:
                        from processor.ocr_reader import ocr_available, extract_title_text
                        if ocr_available():
                            _ocr_text_for_dialog = extract_title_text(preview_img, top_fraction=0.5)
                    except Exception:
                        pass
                user_form_type = self.on_need_form_type(
                    preview_img, Path(pdf_path).name, _ocr_text_for_dialog
                )
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
                try:
                    renewal_date = self.on_need_renewal_date(form_name, preview_img)
                    date_values["renewal"] = renewal_date or ""
                except Exception as _re:
                    self._log(f"Renewal date callback error: {_re}")
                    date_values["renewal"] = ""

            if needs_custom_date(profile) and self.on_need_custom_date:
                try:
                    custom_date = self.on_need_custom_date(form_name)
                    date_values["custom"] = custom_date or ""
                except Exception as _ce:
                    self._log(f"Custom date callback error: {_ce}")
                    date_values["custom"] = ""

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
            # Build a clear reason for the user
            if not config.get("tenant_root", ""):
                reason = "Tenant Root is not configured in General settings."
            elif not unit:
                reason = (
                    f"No QR code could be read from this document. {qr_diagnosis}\n\n"
                    "Please select a destination folder manually."
                )
            else:
                reason = f"Could not determine destination folder for unit '{unit}'."

            self._log(f"⚠ No destination: {reason.splitlines()[0]}")

            if self.on_need_destination:
                # Ask the user to pick a folder; pass preview image and reason
                if preview_img is None:
                    try:
                        from pdf2image import convert_from_path as _c2p
                        _pages = _c2p(pdf_path, dpi=150, first_page=1, last_page=1)
                        preview_img = _pages[0] if _pages else None
                    except Exception:
                        pass
                chosen = self.on_need_destination(
                    filename=Path(pdf_path).name,
                    reason=reason,
                    preview_image=preview_img,
                    proposed_filename=proposed_filename,
                )
                if chosen:
                    dest_folder = chosen.get("folder", "")
                    # Override proposed filename if user changed it
                    if chosen.get("filename"):
                        proposed_filename = chosen["filename"]
                        final_filename_override = proposed_filename
                if not dest_folder:
                    result.notes = reason.splitlines()[0]
                    result.action = "Skipped (no destination)"
                    result.skipped = True
                    return result
            else:
                result.notes = reason.splitlines()[0]
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

        # Apply any filename override set by on_need_destination
        if final_filename_override:
            proposed_filename = final_filename_override

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

            # Check if this scanned file matches a form waiting for signature
            try:
                from form_filler.tracker import mark_signed, find_record_by_unit_and_year
                from datetime import date as _date
                if unit and form_name:
                    form_lower = form_name.lower()
                    if "increase" in form_lower or "renewal" in form_lower or "extension" in form_lower:
                        current_year = _date.today().year
                        rec = find_record_by_unit_and_year(unit, current_year)
                        if rec and rec.get("status") not in ("signed",):
                            mark_signed(unit, current_year, final_path)
                            self._log(f"[Dashboard] Marked {unit} as Signed")
            except Exception as _te:
                self._log(f"[Dashboard] Tracker update skipped: {_te}")

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
