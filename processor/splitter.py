"""
PDF Splitter - Handles splitting multi-document PDFs into individual files.
Supports all 3 scan modes.
"""

import os
import zipfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter

from processor.barcode_reader import scan_page_for_codes, parse_qr_unit, is_separator_page


class DocumentSegment:
    """Represents a logical document found within a PDF."""

    def __init__(self):
        self.page_indices: list[int] = []
        self.qr_unit: Optional[str] = None
        self.raw_qr: Optional[str] = None    # original undecoded QR string
        self.datamatrix_value: Optional[str] = None

    def is_valid(self) -> bool:
        return len(self.page_indices) > 0


def split_pdf(pdf_path: str, mode: int, dpi: int = 200) -> list[DocumentSegment]:
    """
    Split a PDF into document segments based on the scan mode.

    Mode 1: Single document per PDF - returns one segment with all pages.
    Mode 2: Multiple docs per PDF - QR/DM on first page of each doc.
    Mode 3: Separator pages - blank page with SEPARATOR DM precedes each doc.

    Returns list of DocumentSegment objects.
    """
    pdf_path = str(pdf_path)
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    if total_pages == 0:
        return []

    # Convert pages to images for barcode scanning
    pages_images = convert_from_path(pdf_path, dpi=dpi)

    if mode == 1:
        return _split_mode1(pages_images, total_pages)
    elif mode == 2:
        return _split_mode2(pages_images, total_pages)
    elif mode == 3:
        return _split_mode3(pages_images, total_pages)
    else:
        return _split_mode1(pages_images, total_pages)


def _split_mode1(pages_images, total_pages) -> list[DocumentSegment]:
    """Mode 1: entire PDF is one document. Scan only first page for codes."""
    seg = DocumentSegment()
    seg.page_indices = list(range(total_pages))

    codes = scan_page_for_codes(pages_images[0])
    seg.raw_qr = codes["qr"]
    seg.qr_unit = parse_qr_unit(codes["qr"]) if codes["qr"] else None
    seg.datamatrix_value = codes["datamatrix"]

    return [seg]


def _split_mode2(pages_images, total_pages) -> list[DocumentSegment]:
    """Mode 2: QR/DM on first page of each new document within the PDF."""
    segments = []
    current_seg = None

    for i, page_img in enumerate(pages_images):
        codes = scan_page_for_codes(page_img)
        has_qr = bool(codes["qr"])
        has_dm = bool(codes["datamatrix"])

        if has_qr or has_dm:
            # Start a new segment
            if current_seg and current_seg.is_valid():
                segments.append(current_seg)
            current_seg = DocumentSegment()
            current_seg.page_indices.append(i)
            current_seg.raw_qr = codes["qr"]
            current_seg.qr_unit = parse_qr_unit(codes["qr"]) if codes["qr"] else None
            current_seg.datamatrix_value = codes["datamatrix"]
        else:
            if current_seg is None:
                # Pages before any code found - create a segment without codes
                current_seg = DocumentSegment()
            current_seg.page_indices.append(i)

    if current_seg and current_seg.is_valid():
        segments.append(current_seg)

    return segments if segments else _split_mode1(pages_images, total_pages)


def _split_mode3(pages_images, total_pages) -> list[DocumentSegment]:
    """Mode 3: Separator pages (with SEPARATOR DM) precede each document."""
    segments = []
    current_seg = None
    pending_qr = None

    for i, page_img in enumerate(pages_images):
        codes = scan_page_for_codes(page_img)
        dm_val = codes["datamatrix"]
        qr_val = codes["qr"]

        if dm_val and is_separator_page(dm_val):
            # This is a separator page - save current segment and start tracking next
            if current_seg and current_seg.is_valid():
                segments.append(current_seg)
            current_seg = None
            pending_qr = parse_qr_unit(qr_val) if qr_val else None
            # Also check if this page has a non-separator DM (shouldn't, but just in case)
            # Do NOT include this page in any segment
        else:
            if current_seg is None:
                current_seg = DocumentSegment()
                current_seg.qr_unit = pending_qr
                # If this page has DM (form type) but isn't a separator
                if dm_val:
                    current_seg.datamatrix_value = dm_val
                if not pending_qr and qr_val:
                    current_seg.qr_unit = parse_qr_unit(qr_val)
            else:
                # If this page has codes and we're mid-document in mode3,
                # capture DM as form type if not yet set
                if dm_val and not current_seg.datamatrix_value:
                    current_seg.datamatrix_value = dm_val

            current_seg.page_indices.append(i)

    if current_seg and current_seg.is_valid():
        segments.append(current_seg)

    return segments if segments else _split_mode1(pages_images, total_pages)


def extract_segment_to_pdf(source_pdf: str, segment: DocumentSegment, output_path: str):
    """
    Writes a DocumentSegment's pages from source_pdf to output_path.
    """
    reader = PdfReader(source_pdf)
    writer = PdfWriter()

    for page_idx in segment.page_indices:
        writer.add_page(reader.pages[page_idx])

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        writer.write(f)


def archive_original(source_pdf: str) -> str:
    """
    Compresses the original PDF into Archive/ subfolder.
    Returns the path to the created zip file.
    """
    source_path = Path(source_pdf)
    archive_dir = source_path.parent / "Archive"
    archive_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{source_path.stem}_{timestamp}.zip"
    zip_path = archive_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_path, source_path.name)

    return str(zip_path)
