"""
Barcode Reader - Detects and decodes QR codes and Data Matrix barcodes.

Detection order:
  1. pyzbar      — most reliable, handles noisy/small codes (optional install)
  2. OpenCV      — with aggressive preprocessing: upscale, denoise, threshold variants,
                   crops at all four corners
  3. pylibdmtx   — for Data Matrix codes (optional install)

scan_page_for_codes() now also returns a 'diagnosis' string that explains
precisely why detection failed, for display in the UI.
"""

from __future__ import annotations
import cv2
import numpy as np
from PIL import Image
from typing import Optional


# ── pyzbar ────────────────────────────────────────────────────────────────────

def _try_pyzbar(image: Image.Image) -> Optional[str]:
    try:
        from pyzbar.pyzbar import decode, ZBarSymbol
        arr = np.array(image.convert("RGB"))
        for sym in [ZBarSymbol.QRCODE, ZBarSymbol.CODE128, ZBarSymbol.CODE39]:
            results = decode(arr, symbols=[sym])
            if results:
                return results[0].data.decode("utf-8")
    except ImportError:
        pass
    except Exception:
        pass
    return None


# ── OpenCV helpers ────────────────────────────────────────────────────────────

def _cv2_try(arr_gray) -> Optional[str]:
    """Single OpenCV QR attempt on a grayscale array."""
    try:
        det = cv2.QRCodeDetector()
        data, bbox, _ = det.detectAndDecode(arr_gray)
        if data:
            return data
    except Exception:
        pass
    return None


def _opencv_all_strategies(image: Image.Image) -> Optional[str]:
    """
    Try OpenCV QR detection with many preprocessing variants and crop regions.
    Returns decoded string or None.
    """
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    def _variants(src):
        """Yield preprocessed versions of a grayscale array."""
        yield src
        # Upscale if small (QR needs ~100px minimum to decode reliably)
        sh, sw = src.shape
        if max(sh, sw) < 600:
            scale = 600 / max(sh, sw)
            up = cv2.resize(src, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_CUBIC)
            yield up
            src = up
        # CLAHE — local contrast (fixes uneven scanner illumination)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        yield clahe.apply(src)
        # Otsu threshold
        _, ot = cv2.threshold(src, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield ot
        # Fixed thresholds (handles over/under-exposed scans)
        for t in [80, 110, 140, 170]:
            _, th = cv2.threshold(src, t, 255, cv2.THRESH_BINARY)
            yield th
        # Adaptive threshold (best for locally varying scan density)
        yield cv2.adaptiveThreshold(src, 255,
                                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 15, 4)
        # Denoise + Otsu
        dn = cv2.fastNlMeansDenoising(src, h=10)
        _, dn_ot = cv2.threshold(dn, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield dn_ot
        # Sharpen
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharp = cv2.filter2D(src, -1, kernel)
        _, sh_ot = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        yield sh_ot

    # 1. Full page, all variants
    for proc in _variants(gray):
        r = _cv2_try(proc)
        if r:
            return r

    # 2. Eight corner/edge crops — QR may be in any corner, possibly clipped
    fracs = [1/5, 1/4, 1/3]
    crop_specs = []
    for f in fracs:
        fi = int(f * h)
        fw = int(f * w)
        crop_specs += [
            gray[0:fi, 0:fw],           # top-left
            gray[0:fi, w-fw:w],         # top-right
            gray[h-fi:h, 0:fw],         # bottom-left
            gray[h-fi:h, w-fw:w],       # bottom-right
        ]

    for crop in crop_specs:
        if crop.size < 200:
            continue
        for proc in _variants(crop):
            r = _cv2_try(proc)
            if r:
                return r

    return None


# ── pylibdmtx ────────────────────────────────────────────────────────────────

def _try_pylibdmtx(image: Image.Image) -> Optional[str]:
    try:
        from pylibdmtx.pylibdmtx import decode as dm_decode
        results = dm_decode(image, timeout=3000)
        if results:
            return results[0].data.decode("utf-8")
    except ImportError:
        pass
    except Exception:
        pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def detect_qr_code(image: Image.Image) -> Optional[str]:
    r = _try_pyzbar(image)
    if r:
        return r
    return _opencv_all_strategies(image)


def detect_data_matrix(image: Image.Image) -> Optional[str]:
    return _try_pylibdmtx(image)


def _has_dark_corner(image: Image.Image) -> bool:
    """Return True if the top-left corner has enough dark pixels to suggest a QR is present."""
    arr = np.array(image.convert("L"))
    h, w = arr.shape
    corner = arr[0:h//8, 0:w//8]
    if corner.size == 0:
        return False
    return (np.sum(corner < 100) / corner.size) > 0.02


def scan_page_for_codes(page_image: Image.Image) -> dict:
    """
    Scan a page for QR and Data Matrix codes.

    Returns:
        {
          'qr':          str | None,
          'datamatrix':  str | None,
          'diagnosis':   str          # empty if found; explanation if not
        }
    """
    qr = _try_pyzbar(page_image)
    dm = None

    if not qr:
        qr = _opencv_all_strategies(page_image)
    if not qr:
        dm = _try_pylibdmtx(page_image)

    if qr or dm:
        return {"qr": qr, "datamatrix": dm, "diagnosis": ""}

    # ── Build a human-readable diagnosis ─────────────────────────────────────
    pyzbar_ok = False
    pylibdmtx_ok = False
    try:
        from pyzbar import pyzbar as _pz; pyzbar_ok = True
    except ImportError:
        pass
    try:
        from pylibdmtx import pylibdmtx as _dm; pylibdmtx_ok = True
    except ImportError:
        pass

    libs = ["OpenCV"]
    if pyzbar_ok:
        libs.insert(0, "pyzbar")
    if pylibdmtx_ok:
        libs.append("pylibdmtx")

    missing = []
    if not pyzbar_ok:
        missing.append("pyzbar")
    if not pylibdmtx_ok:
        missing.append("pylibdmtx")

    # Check whether a QR-like pattern exists but couldn't be decoded
    has_corner_content = _has_dark_corner(page_image)

    lines = []
    if has_corner_content:
        lines.append(
            "A barcode pattern was found in the top-left corner but could not be decoded."
        )
        lines.append(
            "Most likely cause: the QR code is partially cut off by the scanner margin. "
            "The three finder-pattern squares at the corners of a QR code must all be fully "
            "visible for any decoder to work. Try placing the document further from the "
            "scanner edge, or reprint with the QR moved 15 mm inward from the corner."
        )
    else:
        lines.append("No QR or barcode pattern was found on this page.")

    if missing:
        lines.append(
            f"Installing {' and '.join(missing)} would improve detection on low-quality scans: "
            f"pip install {' '.join(missing)}"
        )

    lines.append(f"Scanners used: {', '.join(libs)}.")

    diagnosis = " ".join(lines)
    return {"qr": None, "datamatrix": None, "diagnosis": diagnosis}


# ── QR format helpers ─────────────────────────────────────────────────────────

def parse_qr_unit(qr_value: str) -> Optional[str]:
    """
    Parse BLDG:216|UNIT:101 → "101-216"
    BLDG:216|UNIT:0 → "BLDG:216" (building-level file)
    Returns None for unknown formats.
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
        if bldg and unit == "0":
            return f"BLDG:{bldg}"
        if unit and bldg:
            return f"{unit}-{bldg}"
        elif unit:
            return unit
        elif bldg:
            return f"BLDG:{bldg}"
    except Exception:
        pass
    return None


def is_building_level_unit(unit_str: str) -> bool:
    return bool(unit_str and unit_str.startswith("BLDG:"))


def get_building_number(unit_str: str) -> str:
    if unit_str and unit_str.startswith("BLDG:"):
        return unit_str[5:]
    return ""


def is_separator_page(dm_value: str) -> bool:
    return bool(dm_value and "SEPARATOR" in dm_value.upper())
