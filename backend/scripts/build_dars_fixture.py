"""Regenerate the committed, PII-free DARS fixture from a local real audit PDF.

The real audit (``backend/tests/fixtures/dars/dars_self.pdf``) is gitignored
because it contains student PII. This script reads it, redacts the PII, and
writes two committed artifacts that the test suite and extraction development
run against:

    dars_sanitized.pdf   regenerated PDF — built fresh from redacted text, so no
                         original objects, metadata, or hidden layers survive to
                         leak PII
    dars_sanitized.txt   the text PyMuPDF extracts from that PDF (human-readable
                         reference + regression lock)

Run from ``backend/``::

    uv run python scripts/build_dars_fixture.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "dars"
REAL_PDF = FIXTURE_DIR / "dars_self.pdf"
OUT_PDF = FIXTURE_DIR / "dars_sanitized.pdf"
OUT_TXT = FIXTURE_DIR / "dars_sanitized.txt"

# (literal, replacement) PII substitutions applied to the extracted text.
_SUBSTITUTIONS = [
    ("Munn Majithia", "Test Student"),
    ("1230356233", "0000000000"),
]
# The audit-results URL embeds a per-session/job token; collapse it.
_URL_TOKEN = re.compile(r"JobQueueRun!!!![A-Za-z0-9+/=]+")

# Strings that must never appear in committed output (defence-in-depth).
_FORBIDDEN = ["Munn", "Majithia", "1230356233", "ISEhIWludFNlcU5vPTE2OTAzNTcxMQ"]

# Geometry for the regenerated PDF. Monospace Courier at a small size keeps every
# source line on one extracted line (no word wrap) for clean re-extraction.
_PAGE = fitz.paper_rect("letter")  # 612 x 792 pt
_MARGIN = 36.0
_BOX = fitz.Rect(_MARGIN, _MARGIN, _PAGE.width - _MARGIN, _PAGE.height - _MARGIN)
_FONT = "cour"
_FONTSIZE = 7.0
_LINES_PER_PAGE = 75


def sanitize(text: str) -> str:
    """Strip student PII from extracted audit text."""
    for needle, repl in _SUBSTITUTIONS:
        text = text.replace(needle, repl)
    return _URL_TOKEN.sub("JobQueueRun!!!!REDACTED", text)


def _build_pdf(lines: list[str]) -> fitz.Document:
    doc = fitz.open()
    for start in range(0, len(lines), _LINES_PER_PAGE):
        chunk = "\n".join(lines[start : start + _LINES_PER_PAGE])
        page = doc.new_page(width=_PAGE.width, height=_PAGE.height)
        leftover = page.insert_textbox(_BOX, chunk, fontsize=_FONTSIZE, fontname=_FONT)
        if leftover < 0:
            raise RuntimeError(
                f"page starting at line {start} overflowed its textbox "
                f"({leftover:.0f}pt short); lower _LINES_PER_PAGE or _FONTSIZE"
            )
    return doc


def main() -> int:
    if not REAL_PDF.exists():
        print(f"missing {REAL_PDF} — drop your real audit PDF there first", file=sys.stderr)
        return 1

    with fitz.open(REAL_PDF) as src:
        raw = "".join(page.get_text() for page in src)
    sanitized = sanitize(raw)

    leaked = [s for s in _FORBIDDEN if s in sanitized]
    if leaked:
        print(f"refusing to write: PII still present in text {leaked}", file=sys.stderr)
        return 2

    with _build_pdf(sanitized.splitlines()) as out:
        out.save(str(OUT_PDF), garbage=4, deflate=True)
        regen = "".join(page.get_text() for page in out)

    leaked_pdf = [s for s in _FORBIDDEN if s.encode() in OUT_PDF.read_bytes()]
    if leaked_pdf:
        OUT_PDF.unlink()
        print(f"refusing to keep PDF: PII found in bytes {leaked_pdf}", file=sys.stderr)
        return 2

    OUT_TXT.write_text(regen)
    print(
        f"wrote {OUT_PDF.name} ({OUT_PDF.stat().st_size} bytes) and "
        f"{OUT_TXT.name} ({len(regen)} chars, {regen.count(chr(10))} lines)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
