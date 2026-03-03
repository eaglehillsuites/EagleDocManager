"""
Duplicate Checker - Detects duplicate files before moving.
"""

import hashlib
from pathlib import Path
from typing import Optional


def file_exists_at_destination(dest_folder: str, filename: str) -> bool:
    """Check if a file with this exact name already exists at destination."""
    return (Path(dest_folder) / filename).exists()


def get_file_hash(path: str) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class DuplicateCheckResult:
    def __init__(self):
        self.is_duplicate = False
        self.existing_path: Optional[str] = None
        self.reason: str = ""

    def __bool__(self):
        return self.is_duplicate


def check_duplicate(dest_folder: str, proposed_filename: str,
                    unit: str = None, form_type: str = None, date_str: str = None
                    ) -> DuplicateCheckResult:
    """
    Check if a file would be a duplicate at the destination.
    Checks:
    1. Exact filename match
    2. Same unit + form_type + date combination
    """
    result = DuplicateCheckResult()
    dest_path = Path(dest_folder) / proposed_filename

    # Check 1: exact filename
    if dest_path.exists():
        result.is_duplicate = True
        result.existing_path = str(dest_path)
        result.reason = f"File with name '{proposed_filename}' already exists"
        return result

    # Check 2: same unit/form/date in destination folder
    if unit and form_type and date_str and Path(dest_folder).exists():
        unit_norm = unit.replace("-", "").lower()
        form_norm = form_type.lower().replace(" ", "")
        date_norm = date_str.replace("-", "").replace("/", "").lower()

        for existing in Path(dest_folder).glob("*.pdf"):
            name_lower = existing.stem.lower().replace("-", "").replace(" ", "").replace("_", "")
            if unit_norm in name_lower and form_norm in name_lower and date_norm in name_lower:
                result.is_duplicate = True
                result.existing_path = str(existing)
                result.reason = f"Similar file found: {existing.name}"
                return result

    return result


def generate_numbered_names(base_filename: str) -> tuple[str, str]:
    """
    Generate (1) and (2) variants of a filename.
    e.g. "101-216 Inspection 2026-02-26.pdf" -> 
         ("101-216 Inspection 2026-02-26 (1).pdf", "101-216 Inspection 2026-02-26 (2).pdf")
    """
    p = Path(base_filename)
    stem = p.stem
    suffix = p.suffix
    return (f"{stem} (1){suffix}", f"{stem} (2){suffix}")
