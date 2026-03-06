"""
Undo Manager - Tracks and reverses file operations within 24 hours.
"""

import zipfile
import shutil
from pathlib import Path
from typing import Optional

import config_manager
from processor.mover import restore_file


def record_batch(source_folder: str, source_filename: str,
                 generated_files: list[dict], archive_path: Optional[str] = None):
    """
    Record a batch of processed files for potential undo.
    
    generated_files: list of dicts with keys:
      - 'path': full path to the generated file
      - 'filename': just the filename
    """
    entry = {
        "source_folder": source_folder,
        "source_filename": source_filename,
        "generated_files": generated_files,
        "archive_path": archive_path,
        "unit_folder_moved": None,  # Set if Out-Inspection was triggered
        "original_unit_folder": None,
        "new_unit_folder": None,
    }
    config_manager.append_undo_entry(entry)
    return entry


def record_unit_folder_move(source_filename: str,
                             original_unit_folder: str, new_unit_folder: str):
    """Update the most recent undo entry with unit folder move info."""
    entries = config_manager.load_undo_log()
    for entry in reversed(entries):
        if entry.get("source_filename") == source_filename:
            entry["unit_folder_moved"] = True
            entry["original_unit_folder"] = original_unit_folder
            entry["new_unit_folder"] = new_unit_folder
            break
    config_manager.save_undo_log(entries)


def get_recent_entries() -> list:
    """Get all undo entries from the last 24 hours."""
    return config_manager.get_recent_undo_entries()


def perform_undo(entries_to_undo: list) -> list[str]:
    """
    Perform undo on the given list of undo entries.
    Returns list of messages about what was restored.
    """
    messages = []

    for entry in entries_to_undo:
        source_folder = entry.get("source_folder", "")
        source_filename = entry.get("source_filename", "")
        archive_path = entry.get("archive_path")
        generated_files = entry.get("generated_files", [])

        # Step 1: Remove generated files
        for gf in generated_files:
            path = gf.get("path", "")
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                    messages.append(f"Removed: {Path(path).name}")
                except Exception as e:
                    messages.append(f"Could not remove {path}: {e}")

        # Step 2: Restore original from archive
        if archive_path and Path(archive_path).exists():
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extract(source_filename, source_folder)
                messages.append(f"Restored: {source_filename}")
                # Remove the archive zip
                Path(archive_path).unlink()
            except Exception as e:
                messages.append(f"Could not restore {source_filename}: {e}")
        elif source_folder and source_filename:
            # Scan mode 1 (single page, no split) — original was never archived,
            # it remains in the source folder. Nothing to restore.
            orig = Path(source_folder) / source_filename
            if orig.exists():
                messages.append(f"Original retained in source folder: {source_filename}")
            else:
                messages.append(f"Note: {source_filename} is no longer in the source folder")

        # Step 3: Reverse unit folder move if applicable
        if entry.get("unit_folder_moved"):
            new_folder = entry.get("new_unit_folder", "")
            orig_folder = entry.get("original_unit_folder", "")
            if new_folder and Path(new_folder).exists() and orig_folder:
                try:
                    import shutil
                    shutil.move(new_folder, orig_folder)
                    messages.append(f"Reversed folder move: {Path(new_folder).name} → {Path(orig_folder).name}")
                except Exception as e:
                    messages.append(f"Could not reverse folder move: {e}")

    return messages


def group_entries_for_display(entries: list) -> list[dict]:
    """
    Group entries by source file for display in the undo dialog.
    Returns list of groups: {'source': str, 'entries': [...], 'files': [...]}
    """
    groups = {}
    for entry in entries:
        key = entry.get("source_filename", "unknown")
        if key not in groups:
            groups[key] = {
                "source": key,
                "source_folder": entry.get("source_folder", ""),
                "entries": [],
                "files": []
            }
        groups[key]["entries"].append(entry)
        for gf in entry.get("generated_files", []):
            groups[key]["files"].append(gf.get("filename", gf.get("path", "")))

    return list(groups.values())
