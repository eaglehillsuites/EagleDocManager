"""
Previous Tenant Recorder - maintains a CSV log of tenants moved to
Previous Tenant Files, including move-in/out dates extracted from
inspection form filenames.
"""

from __future__ import annotations
import csv
import re
from datetime import datetime
from pathlib import Path

import config_manager

FIELDNAMES = [
    "tenant_name", "unit_id", "building",
    "move_in_date", "move_out_date", "moved_on", "previous_folder"
]


def _get_csv_path() -> str:
    return config_manager.get_previous_tenant_csv()


def _parse_date_from_filename(filename: str, keywords: list[str]) -> str:
    """
    Try to extract a date from a filename near any of the given keywords.
    Looks for patterns like: 2025-03-15, 2025-03, 15-03-2025
    Returns ISO date string or "".
    """
    lower = filename.lower()
    for kw in keywords:
        if kw.lower() in lower:
            # Look for yyyy-mm-dd
            m = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
            if m:
                return m.group(1)
            # yyyy-mm
            m = re.search(r'(\d{4}-\d{2})', filename)
            if m:
                return m.group(1)
    return ""


def extract_dates_from_folder(unit_folder: str) -> tuple[str, str]:
    """
    Scan a unit folder for In-Inspection and Out-Inspection files
    and extract move-in / move-out dates from their filenames.
    Returns (move_in_date, move_out_date) as strings.
    """
    folder = Path(unit_folder)
    if not folder.exists():
        return "", ""

    move_in = ""
    move_out = ""

    in_keywords = ["in-inspection", "in inspection", "move-in", "move in", "incoming"]
    out_keywords = ["out-inspection", "out inspection", "move-out", "move out", "vacating"]

    for f in folder.rglob("*.pdf"):
        name = f.name
        d = _parse_date_from_filename(name, in_keywords)
        if d and not move_in:
            move_in = d
        d = _parse_date_from_filename(name, out_keywords)
        if d and not move_out:
            move_out = d

    return move_in, move_out


def record_previous_tenant(
    tenant_name: str,
    unit_id: str,
    unit_folder: str,
    new_previous_folder: str,
):
    """
    Append a row to the previous tenants CSV.
    Extracts move-in/out dates from existing inspection files in unit_folder.
    """
    # Parse building number from unit_id (e.g. "101-216" → "216")
    parts = unit_id.rsplit("-", 1)
    building = parts[1] if len(parts) == 2 else ""

    move_in, move_out = extract_dates_from_folder(unit_folder)

    csv_path = _get_csv_path()
    file_exists = Path(csv_path).exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "tenant_name":      tenant_name,
            "unit_id":          parts[0] if len(parts) == 2 else unit_id,
            "building":         building,
            "move_in_date":     move_in,
            "move_out_date":    move_out,
            "moved_on":         datetime.now().strftime("%Y-%m-%d"),
            "previous_folder":  new_previous_folder,
        })


def load_all_records() -> list[dict]:
    csv_path = _get_csv_path()
    if not Path(csv_path).exists():
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))
