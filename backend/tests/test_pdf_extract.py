"""Tests for the PDF text-extraction utility.

Generates a tiny PDF in-test with PyMuPDF so the suite is self-contained and does
not depend on the committed DARS fixture.
"""

from pathlib import Path

import fitz
import pytest

from asuadvisr.pdf.extract import (
    PdfExtractionError,
    extract_text_from_bytes,
    extract_text_from_path,
)


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def test_extract_from_generated_pdf() -> None:
    text = extract_text_from_bytes(_make_pdf("CSE 240 IN PROGRESS"))
    assert "CSE" in text
    assert "240" in text
    assert "PROGRESS" in text


def test_empty_bytes_raises() -> None:
    with pytest.raises(PdfExtractionError):
        extract_text_from_bytes(b"")


def test_garbage_bytes_raises() -> None:
    with pytest.raises(PdfExtractionError):
        extract_text_from_bytes(b"this is definitely not a pdf")


def test_bytes_and_path_agree(tmp_path: Path) -> None:
    data = _make_pdf("MAT 267 NEEDS 1 COURSE")
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(data)
    assert extract_text_from_path(pdf_path) == extract_text_from_bytes(data)
