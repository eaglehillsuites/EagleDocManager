"""
OCR Reader - Extracts text from the top portion of a PDF page and matches
it against configured form keyword lists.

Used as a fallback when no Data Matrix barcode is detected.
Only OCRs the top 30% of the first page (where titles live) for speed.
"""

from __future__ import annotations
from typing import Optional
from PIL import Image

import config_manager


def _ocr_image(image: Image.Image) -> str:
    try:
        import pytesseract
        return pytesseract.image_to_string(image, config="--psm 6")
    except ImportError:
        raise RuntimeError(
            "pytesseract is not installed. Run: pip install pytesseract\n"
            "Also install Tesseract for Windows from: "
            "https://github.com/UB-Mannheim/tesseract/wiki"
        )
    except Exception as e:
        raise RuntimeError(f"OCR failed: {e}")


def extract_title_text(page_image: Image.Image, top_fraction: float = 0.30) -> str:
    """OCR only the top portion of the page — fast and sufficient for title detection."""
    width, height = page_image.size
    crop_height = int(height * top_fraction)
    top_strip = page_image.crop((0, 0, width, crop_height))

    if width < 1500:
        scale = 1500 / width
        top_strip = top_strip.resize(
            (int(width * scale), int(crop_height * scale)),
            Image.LANCZOS
        )

    return _ocr_image(top_strip)


def match_form_by_ocr(page_image: Image.Image) -> tuple[Optional[dict], str]:
    """
    Try to identify a form type by OCR-ing the page title and matching
    against each form's configured ocr_keywords list.

    Keyword matching rules:
    - Each entry in ocr_keywords is a "group"
    - A group that is a list: ALL items must appear (AND logic)
    - A group that is a string: that string must appear
    - Any group matching = form identified (OR between groups)
    - Case-insensitive

    Returns (form_dict, extracted_text). form_dict is None if no match.
    """
    try:
        text = extract_title_text(page_image)
    except RuntimeError:
        return None, ""

    text_upper = text.upper()
    forms = config_manager.load_forms()

    best_match = None
    best_score = 0

    for form in forms:
        keyword_groups = form.get("ocr_keywords", [])
        if not keyword_groups:
            continue

        for group in keyword_groups:
            keywords = [group] if isinstance(group, str) else group
            if not keywords:
                continue
            if all(kw.upper() in text_upper for kw in keywords):
                score = sum(len(kw) for kw in keywords)
                if score > best_score:
                    best_score = score
                    best_match = form

    return best_match, text


def ocr_available() -> bool:
    """Check if pytesseract and Tesseract are installed and working."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


# ── Unit / building extraction from form body ─────────────────────────────────

MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
]


def extract_unit_from_ocr(page_image: Image.Image) -> tuple[str, str]:
    """
    OCR the full page and try to read the unit number and building number
    from fields like:
        Unit #: 403       Building Address: 282 Nadia Drive ...
        Unit: 101         Address: 282 Nadia ...

    Returns (unit_str, diagnosis_note).
    unit_str is formatted as "unit-bldg" (e.g. "403-282") when both are found,
    just "unit" if only unit found, or "" if nothing found.
    diagnosis_note is a human-readable string for the UI.
    """
    import re
    try:
        text = _ocr_image(page_image)
    except RuntimeError as e:
        return "", f"OCR unavailable: {e}"

    text_norm = " ".join(text.split())
    text_lower = text_norm.lower()

    # --- Unit number ---
    unit = ""
    unit_patterns = [
        r'unit\s*#[:\s]+(\d+)',
        r'unit[:\s]+(\d+)',
        r'apt\.?\s*#?[:\s]+(\d+)',
        r'suite\s*#?[:\s]+(\d+)',
    ]
    for pat in unit_patterns:
        m = re.search(pat, text_lower)
        if m:
            unit = m.group(1)
            break

    # --- Building number (from street address like "282 Nadia Drive") ---
    bldg = ""
    addr_patterns = [
        r'(?:building\s+)?address[:\s]+(\d+)',
        r'^(\d{2,4})\s+\w+\s+(?:drive|dr|street|st|avenue|ave|road|rd|way|place|pl)',
        r'(\d{2,4})\s+nadia',   # specific to your buildings
    ]
    for pat in addr_patterns:
        m = re.search(pat, text_lower)
        if m:
            bldg = m.group(1)
            break

    if unit and bldg:
        return f"{unit}-{bldg}", f"Unit and building read from form text (unit={unit}, bldg={bldg})"
    elif unit:
        return unit, f"Unit number read from form text (unit={unit}); building not found"
    else:
        return "", "Could not extract unit or building number from form text"


def extract_effective_date(page_image: Image.Image) -> str:
    """
    Read the effective/increase date from a rental increase form.
    Looks for: "rent will be increasing on <date>"
    Returns mmmYYYY string (e.g. "Jun2026") or "".
    """
    import re
    try:
        text = _ocr_image(page_image)
    except RuntimeError:
        return ""

    text_lower = " ".join(text.lower().split())

    patterns = [
        r'increasing on ([a-z]+ \d{1,2},?\s*\d{4})',
        r'increasing on ([a-z]+ \d{4})',
        r'increasing on (\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'increasing on (\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',
        r'effective date[:\s]+([a-z]+ \d{1,2},?\s*\d{4})',
        r'effective[:\s]+([a-z]+ \d{4})',
    ]

    candidate = ""
    for pat in patterns:
        m = re.search(pat, text_lower)
        if m:
            candidate = m.group(1).strip()
            break

    if not candidate:
        return ""

    # Parse month-name formats: "june 1, 2026" or "june 2026"
    for i, mname in enumerate(_MONTH_NAMES):
        short = MONTH_SHORT[i]
        m = re.search(rf'\b{mname}\b.*?\b(\d{{4}})\b', candidate)
        if not m:
            m = re.search(rf'\b{short.lower()}\b.*?\b(\d{{4}})\b', candidate)
        if m:
            return f"{short}{m.group(1)}"

    # Numeric: mm/dd/yyyy or mm-dd-yyyy
    m = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', candidate)
    if m:
        month, year = int(m.group(1)), int(m.group(3))
        if year < 100:
            year += 2000
        if 1 <= month <= 12:
            return f"{MONTH_SHORT[month - 1]}{year}"

    # ISO: yyyy-mm-dd
    m = re.search(r'(\d{4})[/\-](\d{1,2})[/\-]\d{1,2}', candidate)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return f"{MONTH_SHORT[month - 1]}{year}"

    return ""


def extract_candidate_keywords(ocr_text: str, max_keywords: int = 8) -> list[str]:
    """
    From raw OCR text, extract a short list of candidate keywords that are
    likely to be distinctive title words for this form type.

    Filters out common English words, numbers-only tokens, very short words.
    Returns a list of uppercase keyword strings.
    """
    import re

    STOP_WORDS = {
        "THE", "OF", "AND", "TO", "IN", "IS", "FOR", "WITH", "BY", "OR",
        "AN", "AT", "BE", "AS", "ON", "ARE", "NOT", "BUT", "FROM", "THIS",
        "THAT", "WILL", "YOUR", "YOU", "WE", "IT", "ALL", "SO", "IF",
        "ANY", "HAS", "CAN", "NEW", "DATE", "NAME", "SIGN", "PLEASE",
        "RETURN", "FORM", "COPY", "ABOVE", "BELOW", "NOTE", "NOTES",
        "AMOUNT", "CURRENT", "TOTAL", "MONTHLY", "PAYMENT", "PRINT",
    }

    words = re.findall(r'[A-Za-z]{4,}', ocr_text.upper())
    seen = set()
    result = []
    for word in words:
        if word in STOP_WORDS or word in seen:
            continue
        seen.add(word)
        result.append(word)
        if len(result) >= max_keywords:
            break
    return result
