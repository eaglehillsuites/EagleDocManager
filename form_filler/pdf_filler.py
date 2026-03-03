"""
PDF Form Filler - Fills PDF form fields from a data dictionary.
Handles field mapping, TenantName combination, and optional flattening.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from copy import deepcopy

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, create_string_object


def _set_field(writer: PdfWriter, field_name: str, value: str):
    """Set a single form field value in a PdfWriter."""
    try:
        writer.update_page_form_field_values(
            writer.pages[0],
            {field_name: value},
            auto_regenerate=False,
        )
    except Exception as e:
        print(f"[FormFiller] Could not set field '{field_name}': {e}")


def fill_pdf(
    template_path: str,
    output_path: str,
    field_values: dict[str, str],
    flatten: bool = False,
) -> str:
    """
    Fill a PDF form template with the given field values and save to output_path.
    Returns the output path.
    """
    reader = PdfReader(template_path)
    writer = PdfWriter()
    writer.append(reader)

    # Build the values dict, skipping None values
    clean_values = {k: (str(v) if v is not None else "") for k, v in field_values.items()}

    writer.update_page_form_field_values(
        writer.pages[0],
        clean_values,
        auto_regenerate=False,
    )

    if flatten:
        # Flatten by removing the AcroForm interactive flag
        if "/AcroForm" in writer._root_object:
            writer._root_object["/AcroForm"].update(
                {NameObject("/NeedAppearances"): create_string_object("false")}
            )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        writer.write(f)

    return str(output_path)


def build_increase_fields(
    csv_row: dict,
    delivery_date_str: str,
    due_date_str: str,
    increase_date_str: str,
    flatten: bool = False,
) -> dict[str, str]:
    """
    Build the complete field map for a Rental Increase form.

    CSV fields used directly:
        RentCurrent, IncreaseDollars, RentIncreased, IncreasePercent,
        ParkStoreDollars, TotalMonthly, BuildingAddr, Unit,
        TenantName1, TenantName2, TenantName3

    Combined:
        TenantName = TenantName1 + TenantName2 + TenantName3 (comma-separated,
                     skipping blanks)

    Program-generated:
        DeliveryDate, DueDate, IncreaseDate
    """
    # Build combined TenantName
    names = [
        csv_row.get("TenantName1", "").strip(),
        csv_row.get("TenantName2", "").strip(),
        csv_row.get("TenantName3", "").strip(),
    ]
    combined_name = ", ".join(n for n in names if n)

    return {
        "TenantName":       combined_name,
        "TenantName1":      csv_row.get("TenantName1", ""),
        "TenantName2":      csv_row.get("TenantName2", ""),
        "TenantName3":      csv_row.get("TenantName3", ""),
        "BuildingAddr":     csv_row.get("BuildingAddr", ""),
        "Unit":             csv_row.get("Unit", ""),
        "RentCurrent":      csv_row.get("RentCurrent", ""),
        "IncreaseDollars":  csv_row.get("IncreaseDollars", ""),
        "RentIncreased":    csv_row.get("RentIncreased", ""),
        "IncreasePercent":  csv_row.get("IncreasePercent", ""),
        "ParkStoreDollars": csv_row.get("ParkStoreDollars", ""),
        "TotalMonthly":     csv_row.get("TotalMonthly", ""),
        "DeliveryDate":     delivery_date_str,
        "DueDate":          due_date_str,
        "IncreaseDate":     increase_date_str,
    }


def build_renewal_fields(
    csv_row: dict,
    due_date_str: str,
    lease_start_str: str,
    lease_end_str: str,
    new_lease_end_str: str,
    increase_date_str: str,
) -> dict[str, str]:
    """
    Build the complete field map for a Fixed-Term Extension (Renewal) form.

    CSV fields:
        BuildingAddr, Unit, TenantName1/2/3,
        RentCurrent, TotalMonthly, IncreaseDate

    User popup:
        DueDate (same as increase), lease_start, lease_end, new_lease_end

    Blank (signed in person):
        text_13gwqo, text_14yipe, text_15rggw, text_16jpcq (date lines)
    """
    return {
        "BuildingAddr":  csv_row.get("BuildingAddr", ""),
        "Unit":          csv_row.get("Unit", ""),
        "TenantName1":   csv_row.get("TenantName1", ""),
        "TenantName2":   csv_row.get("TenantName2", ""),
        "TenantName3":   csv_row.get("TenantName3", ""),
        "RentCurrent":   csv_row.get("RentCurrent", ""),
        "TotalMonthly":  csv_row.get("TotalMonthly", ""),
        "IncreaseDate":  increase_date_str,
        "DueDate":       due_date_str,
        "text_7lebt":    lease_start_str,    # "beginning ___ for one year"
        "text_8vqqj":    lease_end_str,      # "end date of ___"
        "text_9oruw":    new_lease_end_str,  # "to a new end date of ___"
        # Signature date lines — left blank
        "text_13gwqo":   "",
        "text_14yipe":   "",
        "text_15rggw":   "",
        "text_16jpcq":   "",
    }


def get_blank_fields(fields: dict[str, str]) -> list[str]:
    """Return list of field names that have empty/None values."""
    return [k for k, v in fields.items() if not str(v).strip()]


def has_blank_required_fields(fields: dict[str, str],
                               skip_fields: list[str] = None) -> bool:
    """
    Check if any required fields are blank.
    skip_fields: field names intentionally left blank (e.g. signature dates).
    """
    skip = set(skip_fields or [])
    for k, v in fields.items():
        if k not in skip and not str(v).strip():
            return True
    return False


# Fields intentionally left blank on the renewal form
RENEWAL_INTENTIONALLY_BLANK = {
    "text_13gwqo", "text_14yipe", "text_15rggw", "text_16jpcq"
}

# Fields intentionally left blank on the increase form (none currently)
INCREASE_INTENTIONALLY_BLANK: set[str] = set()
