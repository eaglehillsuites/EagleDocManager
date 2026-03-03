"""
Form Filler Tracker - Persistent tracking of generated forms, their status,
and renewal flags. Stored in AppData as form_tracker.json.

Status values:
  "entered"    - Generated and saved, not yet printed/delivered
  "delivered"  - Marked as printed/delivered to tenant
  "signed"     - Signed copy scanned and processed
  "overdue"    - Unsigned from a previous month (auto-flagged)

Each record tracks one "unit batch" (increase + optional renewal = 1 unit).
"""

from __future__ import annotations
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import config_manager

TRACKER_FILE = config_manager.APP_DIR / "form_tracker.json"


# ── Data structure ────────────────────────────────────────────

def _empty_record(
    unit: str,
    month: int,
    year: int,
    increase_path: str,
    renewal_path: Optional[str] = None,
    tenant_name: str = "",
    building_addr: str = "",
) -> dict:
    return {
        "unit": unit,
        "month": month,
        "year": year,
        "increase_path": increase_path,
        "renewal_path": renewal_path,
        "tenant_name": tenant_name,
        "building_addr": building_addr,
        "status": "entered",
        "awaiting_review": False,
        "lease_type": None,           # "Fixed-Term" | "Periodic (Y)" | "Periodic (M)"
        "created_at": datetime.now().isoformat(),
        "delivered_at": None,
        "signed_at": None,
    }


# ── Load / Save ───────────────────────────────────────────────

def load_tracker() -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(records: list[dict]):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)


def add_record(record: dict):
    records = load_tracker()
    records.append(record)
    save_tracker(records)
    return record


def update_record(unit: str, month: int, year: int, **kwargs):
    records = load_tracker()
    for r in records:
        if r["unit"] == unit and r["month"] == month and r["year"] == year:
            r.update(kwargs)
            break
    save_tracker(records)


# ── Queries ───────────────────────────────────────────────────

def get_records_for_month(month: int, year: int) -> list[dict]:
    return [r for r in load_tracker() if r["month"] == month and r["year"] == year]


def get_all_months() -> list[tuple[int, int]]:
    """Return sorted list of (month, year) tuples that have records."""
    records = load_tracker()
    seen = set()
    result = []
    for r in records:
        key = (r["month"], r["year"])
        if key not in seen:
            seen.add(key)
            result.append(key)
    return sorted(result, key=lambda x: (x[1], x[0]), reverse=True)


def find_record_by_unit_and_year(unit: str, year: int) -> Optional[dict]:
    """Used when scanning signed docs — match by unit + year."""
    records = load_tracker()
    for r in records:
        if r["unit"] == unit and r["year"] == year:
            return r
    return None


def mark_signed(unit: str, year: int, signed_path: str):
    """
    Called by the scan/sort pipeline when a signed form is detected.
    Deletes the unsigned copy from Waiting for Signature folder.
    """
    records = load_tracker()
    for r in records:
        if r["unit"] == unit and r["year"] == year and r["status"] != "signed":
            r["status"] = "signed"
            r["signed_at"] = datetime.now().isoformat()

            # Delete unsigned copies
            for path_key in ("increase_path", "renewal_path"):
                p = r.get(path_key)
                if p and Path(p).exists():
                    try:
                        Path(p).unlink()
                    except Exception as e:
                        print(f"[Tracker] Could not delete {p}: {e}")
            break
    save_tracker(records)


def flag_overdue():
    """
    Mark any 'entered' or 'delivered' records from previous months as overdue.
    Called on app startup.
    """
    today = date.today()
    records = load_tracker()
    changed = False
    for r in records:
        if r["status"] in ("entered", "delivered"):
            rec_year = r["year"]
            rec_month = r["month"]
            # Overdue if we are now past the end of that month
            if (rec_year, rec_month) < (today.year, today.month):
                r["status"] = "overdue"
                changed = True
    if changed:
        save_tracker(records)


# ── Dashboard metrics ─────────────────────────────────────────

def get_metrics(month: int, year: int) -> dict:
    records = get_records_for_month(month, year)
    all_records = load_tracker()

    overdue = sum(1 for r in all_records if r["status"] == "overdue")
    entered = sum(1 for r in records if r["status"] == "entered")
    delivered = sum(1 for r in records if r["status"] == "delivered")
    signed = sum(1 for r in records if r["status"] == "signed")
    awaiting_review = sum(1 for r in records if r.get("awaiting_review"))

    return {
        "overdue": overdue,
        "entered": entered,
        "delivered": delivered,
        "signed": signed,
        "awaiting_review": awaiting_review,
        "total": len(records),
    }


# ── Convenience constructors ──────────────────────────────────

def create_record(unit, month, year, increase_path,
                  renewal_path=None, tenant_name="", building_addr="") -> dict:
    rec = _empty_record(unit, month, year, increase_path,
                        renewal_path, tenant_name, building_addr)
    add_record(rec)
    return rec
