"""PDF text extraction (PyMuPDF wrapper).

Isolates the ``fitz`` dependency so the LLM modules never import it directly and
so callers get a single typed error (``PdfExtractionError``) to map to HTTP 422.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot be opened or yields no extractable text."""


def extract_text_from_bytes(data: bytes) -> str:
    """Extract plain text from PDF bytes (e.g. an uploaded file's contents)."""
    if not data:
        raise PdfExtractionError("empty PDF input")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # fitz raises FileDataError / RuntimeError on bad input
        raise PdfExtractionError(f"could not open PDF: {exc}") from exc
    try:
        text = "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    if not text.strip():
        raise PdfExtractionError("PDF contained no extractable text")
    return text


def extract_text_from_path(path: str | Path) -> str:
    """Extract plain text from a PDF on disk (convenience for tests and the CLI)."""
    return extract_text_from_bytes(Path(path).read_bytes())
