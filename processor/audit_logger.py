"""
Audit Logger - Writes CSV audit logs to the source folder.
"""

import csv
import os
from datetime import datetime
from pathlib import Path


AUDIT_FILENAME = "eagle_doc_audit.csv"

HEADERS = [
    "Timestamp",
    "Original File",
    "Generated File",
    "Unit",
    "Form Type",
    "Scan Mode",
    "Action",
    "Notes"
]


def get_audit_path(source_folder: str) -> str:
    return str(Path(source_folder) / AUDIT_FILENAME)


def log_entry(source_folder: str, original_file: str, generated_file: str,
              unit: str, form_type: str, scan_mode: int, action: str, notes: str = ""):
    """
    Append a single entry to the audit log CSV in the source folder.
    """
    audit_path = get_audit_path(source_folder)
    file_exists = os.path.isfile(audit_path)

    with open(audit_path, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(HEADERS)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            original_file,
            generated_file,
            unit or "",
            form_type or "",
            scan_mode,
            action,
            notes
        ])


def log_undo(source_folder: str, file_path: str, original_name: str):
    """Log an undo action."""
    log_entry(
        source_folder=source_folder,
        original_file=original_name,
        generated_file=file_path,
        unit="",
        form_type="",
        scan_mode=0,
        action="UNDO",
        notes=f"Restored to {original_name}"
    )


def log_batch(source_folder: str, batch_results: list):
    """
    Log a full batch of processing results.
    Each result should be a dict with keys matching log_entry params.
    """
    for r in batch_results:
        log_entry(
            source_folder=source_folder,
            original_file=r.get("original_file", ""),
            generated_file=r.get("generated_file", ""),
            unit=r.get("unit", ""),
            form_type=r.get("form_type", ""),
            scan_mode=r.get("scan_mode", 0),
            action=r.get("action", "Moved"),
            notes=r.get("notes", "")
        )
