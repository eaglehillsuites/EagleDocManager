"""
CSV Reader - Reads tenant data CSV for the form filler.
Handles blank row detection and field validation.
"""

from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterator


REQUIRED_INCREASE_FIELDS = {
    "BuildingAddr", "Unit", "TenantName1",
    "RentCurrent", "IncreaseDollars", "RentIncreased",
    "IncreasePercent", "TotalMonthly",
}

# Fields that may legitimately be blank
OPTIONAL_FIELDS = {"TenantName2", "TenantName3", "ParkStoreDollars"}


def read_csv(path: str) -> list[dict]:
    """
    Read a CSV file and return a list of non-blank rows as dicts.
    Stops at the first completely blank row.
    Strips whitespace from all values.
    """
    rows = []
    path = Path(path)

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip whitespace
            clean = {k.strip(): v.strip() for k, v in row.items() if k}

            # Stop at blank row
            if not any(clean.values()):
                break

            rows.append(clean)

    return rows


def validate_row(row: dict) -> list[str]:
    """
    Check a row for missing required fields.
    Returns list of missing field names (empty = valid).
    """
    missing = []
    for field in REQUIRED_INCREASE_FIELDS:
        if field not in row or not row[field].strip():
            missing.append(field)
    return missing


def get_unit_id(row: dict) -> str:
    """Build unit ID string from row data, e.g. '101-216'."""
    unit = row.get("Unit", "").strip()
    bldg = row.get("BuildingNumber", row.get("Building Number", "")).strip()
    if unit and bldg:
        return f"{unit}-{bldg}"
    return unit or "UNKNOWN"


def has_blank_csv_fields(row: dict,
                          skip: set[str] = None) -> bool:
    """Return True if any non-optional field is blank."""
    skip = skip or OPTIONAL_FIELDS
    for k, v in row.items():
        if k not in skip and not v.strip():
            return True
    return False
