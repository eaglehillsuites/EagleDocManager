"""
Config Manager - Handles all configuration file operations.
Stores config in AppData/Local/EagleDocManager/
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

APP_NAME = "EagleDocManager"

def get_app_data_dir() -> Path:
    """Returns the AppData/Local/EagleDocManager path."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "logs").mkdir(exist_ok=True)
    return app_dir


APP_DIR = get_app_data_dir()

CONFIG_FILE = APP_DIR / "config.json"
FORMS_FILE = APP_DIR / "forms.json"
NAMING_FILE = APP_DIR / "naming_profiles.json"
UNDO_FILE = APP_DIR / "undo_log.json"
GMAIL_TOKEN_FILE = APP_DIR / "gmail_token.json"

DEFAULT_CONFIG = {
    "tenant_root": "",
    "previous_tenants_path": "",
    "start_with_windows": False,
    "gmail_connected": False,
    "watched_folders": [],
    "exceptions": [],
    "scan_mode": 1,
    "version": "1.0.0"
}

DEFAULT_FORMS = [
    {
        "id": "inspection_out",
        "name": "Out-Inspection",
        "datamatrix_value": "FORM:OutInspection",
        "naming_profile_id": "inspection_profile"
    },
    {
        "id": "inspection_in",
        "name": "In-Inspection",
        "datamatrix_value": "FORM:InInspection",
        "naming_profile_id": "inspection_profile"
    },
    {
        "id": "rental_increase",
        "name": "Rental Increase",
        "datamatrix_value": "FORM:RentalIncrease",
        "naming_profile_id": "rental_increase_profile"
    },
    {
        "id": "maintenance",
        "name": "Maintenance",
        "datamatrix_value": "FORM:Maintenance",
        "naming_profile_id": "default_profile"
    },
    {
        "id": "notice_entry",
        "name": "Notice of Entry",
        "datamatrix_value": "FORM:NoticeEntry",
        "naming_profile_id": "default_profile"
    },
    {
        "id": "lease_renewal",
        "name": "Lease Renewal",
        "datamatrix_value": "FORM:LeaseRenewal",
        "naming_profile_id": "default_profile"
    }
]

DEFAULT_NAMING_PROFILES = [
    {
        "id": "default_profile",
        "name": "Default (yyyy-mm-dd)",
        "date_format": "yyyy-mm-dd",
        "parts": [
            {"type": "unit"},
            {"type": "text", "value": " - "},
            {"type": "form_name"},
            {"type": "text", "value": " "},
            {"type": "date", "source": "today"}
        ]
    },
    {
        "id": "inspection_profile",
        "name": "Inspection (yyyy-mm-dd)",
        "date_format": "yyyy-mm-dd",
        "parts": [
            {"type": "unit"},
            {"type": "text", "value": " "},
            {"type": "form_name"},
            {"type": "text", "value": " "},
            {"type": "date", "source": "today"}
        ]
    },
    {
        "id": "rental_increase_profile",
        "name": "Rental Increase (mmmYYYY)",
        "date_format": "mmmYYYY",
        "parts": [
            {"type": "unit"},
            {"type": "text", "value": " Increase "},
            {"type": "date", "source": "renewal"}
        ]
    }
]


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    # Merge with defaults for any missing keys
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_forms() -> list:
    if not FORMS_FILE.exists():
        save_forms(DEFAULT_FORMS)
        return DEFAULT_FORMS.copy()
    with open(FORMS_FILE, "r") as f:
        return json.load(f)


def save_forms(forms: list):
    with open(FORMS_FILE, "w") as f:
        json.dump(forms, f, indent=2)


def load_naming_profiles() -> list:
    if not NAMING_FILE.exists():
        save_naming_profiles(DEFAULT_NAMING_PROFILES)
        return DEFAULT_NAMING_PROFILES.copy()
    with open(NAMING_FILE, "r") as f:
        return json.load(f)


def save_naming_profiles(profiles: list):
    with open(NAMING_FILE, "w") as f:
        json.dump(profiles, f, indent=2)


def load_undo_log() -> list:
    if not UNDO_FILE.exists():
        return []
    with open(UNDO_FILE, "r") as f:
        return json.load(f)


def save_undo_log(entries: list):
    with open(UNDO_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def append_undo_entry(entry: dict):
    entries = load_undo_log()
    entry["timestamp"] = datetime.now().isoformat()
    entries.append(entry)
    save_undo_log(entries)


def get_recent_undo_entries() -> list:
    """Return only entries from the last 24 hours."""
    from datetime import timedelta
    entries = load_undo_log()
    cutoff = datetime.now() - timedelta(hours=24)
    recent = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            if ts >= cutoff:
                recent.append(e)
        except Exception:
            pass
    return recent


def get_form_by_datamatrix(dm_value: str) -> dict | None:
    forms = load_forms()
    for f in forms:
        if f.get("datamatrix_value", "").strip() == dm_value.strip():
            return f
    return None


def get_naming_profile(profile_id: str) -> dict | None:
    profiles = load_naming_profiles()
    for p in profiles:
        if p["id"] == profile_id:
            return p
    return None
