"""
Mover - Handles moving processed files to their destination folders.
"""

import os
import shutil
from pathlib import Path


def move_file(source: str, destination_folder: str, filename: str) -> str:
    """
    Move a file to the destination folder with the given filename.
    Returns the new file path.
    """
    dest_folder = Path(destination_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)

    dest_path = dest_folder / filename

    shutil.move(source, str(dest_path))
    return str(dest_path)


def copy_file(source: str, destination_folder: str, filename: str) -> str:
    """
    Copy a file to the destination folder with the given filename.
    Returns the new file path.
    """
    dest_folder = Path(destination_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)

    dest_path = dest_folder / filename
    shutil.copy2(source, str(dest_path))
    return str(dest_path)


def restore_file(current_path: str, original_folder: str, original_name: str) -> str:
    """
    Move a file back to its original location for undo operations.
    Returns the restored path.
    """
    orig_folder = Path(original_folder)
    orig_folder.mkdir(parents=True, exist_ok=True)

    restore_path = orig_folder / original_name
    shutil.move(current_path, str(restore_path))
    return str(restore_path)


def move_unit_folder_to_previous(unit_folder: str, previous_tenants_root: str,
                                 tenant_name: str, unit_id: str) -> str:
    """
    Move a unit folder to the Previous Tenants directory, renamed with tenant name.
    Returns the new path.
    """
    prev_root = Path(previous_tenants_root)
    prev_root.mkdir(parents=True, exist_ok=True)

    # Sanitize tenant name
    safe_name = tenant_name.strip().replace("/", "-").replace("\\", "-")
    new_folder_name = f"{unit_id} - {safe_name}"
    dest = prev_root / new_folder_name

    # If destination already exists, add suffix
    if dest.exists():
        i = 1
        while (prev_root / f"{new_folder_name} ({i})").exists():
            i += 1
        dest = prev_root / f"{new_folder_name} ({i})"

    shutil.move(unit_folder, str(dest))
    return str(dest)


def ensure_folder(path: str) -> str:
    """Create folder if it doesn't exist. Returns path."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path
