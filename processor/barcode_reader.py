"""
Barcode Reader - Detects and decodes QR codes and Data Matrix barcodes from PDF pages.
"""

import numpy as np
from PIL import Image
from typing import Optional


def _try_pyzbar_qr(image: Image.Image) -> Optional[str]:
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode, ZBarSymbol
        img_array = np.array(image)
        results = pyzbar_decode(img_array, symbols=[ZBarSymbol.QRCODE])
        if results:
            return results[0].data.decode("utf-8")
    except Exception:
        pass
    return None


def _try_opencv_qr(image: Image.Image) -> Optional[str]:
    try:
        import cv2
        img_array = np.array(image.convert("RGB"))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img_bgr)
        if data:
            return data
    except Exception:
        pass
    return None


def _try_pylibdmtx(image: Image.Image) -> Optional[str]:
    try:
        from pylibdmtx.pylibdmtx import decode as dm_decode
        results = dm_decode(image)
        if results:
            return results[0].data.decode("utf-8")
    except Exception:
        pass
    return None


def detect_qr_code(image: Image.Image) -> Optional[str]:
    """
    Detect QR code from a PIL Image. Tries pyzbar first, then OpenCV.
    Returns decoded string or None.
    """
    result = _try_pyzbar_qr(image)
    if result:
        return result
    result = _try_opencv_qr(image)
    return result


def detect_data_matrix(image: Image.Image) -> Optional[str]:
    """
    Detect Data Matrix barcode from a PIL Image using pylibdmtx.
    Returns decoded string or None.
    """
    return _try_pylibdmtx(image)


def scan_page_for_codes(page_image: Image.Image) -> dict:
    """
    Scans a single page image for QR and Data Matrix codes.
    Returns dict: { 'qr': str|None, 'datamatrix': str|None }
    
    Crops top-right quadrant for faster detection, then falls back to full page.
    """
    width, height = page_image.size

    # Crop top-right quadrant
    top_right = page_image.crop((width // 2, 0, width, height // 2))

    qr = detect_qr_code(top_right)
    dm = detect_data_matrix(top_right)

    # Fallback: scan full page if not found in crop
    if not qr:
        qr = detect_qr_code(page_image)
    if not dm:
        dm = detect_data_matrix(page_image)

    return {"qr": qr, "datamatrix": dm}


def parse_qr_unit(qr_value: str) -> Optional[str]:
    """
    Parses QR value in format: BLDG:216|UNIT:101
    Returns formatted string like "101-216" or None.
    """
    if not qr_value:
        return None
    try:
        parts = {}
        for segment in qr_value.split("|"):
            if ":" in segment:
                key, val = segment.split(":", 1)
                parts[key.strip().upper()] = val.strip()
        unit = parts.get("UNIT")
        bldg = parts.get("BLDG")
        if unit and bldg:
            return f"{unit}-{bldg}"
        elif unit:
            return unit
    except Exception:
        pass
    return qr_value  # Return raw value as fallback


def is_separator_page(dm_value: str) -> bool:
    """Check if a Data Matrix value indicates a separator page."""
    if not dm_value:
        return False
    return "SEPARATOR" in dm_value.upper()
