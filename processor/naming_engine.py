"""
Naming Engine - Generates filenames based on naming convention profiles.
Supports tokens: unit, form_name, text, date (today/renewal/custom), building.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import config_manager


MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def format_date(date_str: str, date_format: str) -> str:
    """
    Formats a date string based on a date format pattern.
    date_str: "yyyy-mm-dd" or a month abbreviation like "Jul2026"
    date_format: pattern like "yyyy-mm-dd", "mmmYYYY", "dd-mmm-yyyy"
    """
    # If date is already in target format, return as-is
    if not date_str:
        return ""

    # Try to parse ISO date
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            return date_str  # Can't parse, return raw

    return _apply_date_format(dt, date_format)


def _apply_date_format(dt: datetime, fmt: str) -> str:
    """Apply a custom date format pattern."""
    result = fmt
    result = result.replace("yyyy", dt.strftime("%Y"))
    result = result.replace("YYYY", dt.strftime("%Y"))
    result = result.replace("mm", dt.strftime("%m"))
    result = result.replace("dd", dt.strftime("%d"))
    result = result.replace("mmm", MONTH_SHORT[dt.month - 1])
    result = result.replace("MMM", MONTH_SHORT[dt.month - 1])
    return result


def format_month_year(month_index: int, year: int, date_format: str) -> str:
    """
    Format a month/year (for renewal dates).
    month_index: 1-12
    """
    dt = datetime(year, month_index, 1)
    return _apply_date_format(dt, date_format)


def sanitize_filename(name: str) -> str:
    """Remove characters not allowed in Windows filenames."""
    invalid = r'[<>:"/\\|?*]'
    name = re.sub(invalid, "", name)
    name = name.strip(" .")
    return name


class NamingEngine:
    """
    Builds a filename from a naming profile and provided data tokens.
    
    date_values: dict mapping date source names to resolved values
      e.g. {"today": "2026-02-26", "renewal": "Jul2026", "custom": "Some Text"}
    """

    def __init__(self, profile: dict, unit: str, form_name: str,
                 date_values: Optional[dict] = None):
        self.profile = profile
        self.unit = unit or "NOUNIT"
        self.form_name = form_name or "Unknown"
        self.date_values = date_values or {}
        self.date_format = profile.get("date_format", "yyyy-mm-dd")

    def build(self) -> str:
        parts = self.profile.get("parts", [])
        result = ""

        for part in parts:
            part_type = part.get("type", "")

            if part_type == "unit":
                result += self.unit

            elif part_type == "form_name":
                result += self.form_name

            elif part_type == "text":
                result += part.get("value", "")

            elif part_type == "date":
                source = part.get("source", "today")
                if source == "today":
                    val = self.date_values.get("today", datetime.now().strftime("%Y-%m-%d"))
                    result += format_date(val, self.date_format)
                elif source == "renewal":
                    val = self.date_values.get("renewal", "")
                    result += val  # Already formatted by popup
                elif source == "custom":
                    val = self.date_values.get("custom", "")
                    result += val
                else:
                    val = self.date_values.get(source, "")
                    result += val

        filename = sanitize_filename(result)
        if not filename:
            filename = f"{self.unit}_{self.form_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return filename + ".pdf"


def needs_renewal_date(profile: dict) -> bool:
    """Check if a naming profile requires a renewal date input."""
    for part in profile.get("parts", []):
        if part.get("type") == "date" and part.get("source") == "renewal":
            return True
    return False


def needs_custom_date(profile: dict) -> bool:
    """Check if a naming profile requires a custom date input."""
    for part in profile.get("parts", []):
        if part.get("type") == "date" and part.get("source") == "custom":
            return True
    return False


def build_filename(form: dict, unit: str, date_values: dict = None) -> str:
    """
    High-level helper: given a form dict and unit string, build the final filename.
    """
    profile_id = form.get("naming_profile_id", "default_profile")
    profile = config_manager.get_naming_profile(profile_id)

    if not profile:
        # Fallback to basic naming
        today = datetime.now().strftime("%Y-%m-%d")
        return sanitize_filename(f"{unit} {form.get('name', 'Unknown')} {today}") + ".pdf"

    engine = NamingEngine(
        profile=profile,
        unit=unit,
        form_name=form.get("name", "Unknown"),
        date_values=date_values or {"today": datetime.now().strftime("%Y-%m-%d")}
    )
    return engine.build()


def determine_destination_folder(config: dict, unit_str: str) -> str:
    """
    Determine the destination folder for a unit string like "101-216".
    Creates folder if it doesn't exist.
    Returns the full path.
    """
    tenant_root = config.get("tenant_root", "")
    if not tenant_root:
        return ""

    folder = Path(tenant_root) / unit_str
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)
