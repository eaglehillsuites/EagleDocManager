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
