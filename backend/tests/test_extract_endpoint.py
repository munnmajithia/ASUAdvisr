"""Tests for the /extract-requirements endpoint.

Calls the async route handler directly — Starlette's TestClient deadlocks under
this repo's ``asyncio_mode = "auto"`` config. The LLM extractor is monkeypatched,
so no live API call is made; a tiny real PDF is generated in-test so the
deterministic PDF→text step runs for real.
"""

from io import BytesIO

import fitz
import pytest
from fastapi import HTTPException, UploadFile

from asuadvisr.api import main
from asuadvisr.api.main import extract_requirements
from asuadvisr.llm.requirement_profile import RequirementProfile


def _pdf_upload(text: str, filename: str = "dars.pdf") -> UploadFile:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return UploadFile(file=BytesIO(data), filename=filename)


async def test_extract_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "extract_profile",
        lambda _text: RequirementProfile(
            major="Computer Science", required_courses_remaining=["CSE 310"]
        ),
    )
    result = await extract_requirements(_pdf_upload("CSE 110 IN PROGRESS"))
    assert result.major == "Computer Science"
    assert result.required_courses_remaining == ["CSE 310"]


async def test_extract_bad_pdf_returns_422() -> None:
    upload = UploadFile(file=BytesIO(b"not a pdf at all"), filename="x.pdf")
    with pytest.raises(HTTPException) as exc_info:
        await extract_requirements(upload)
    assert exc_info.value.status_code == 422


async def test_extract_llm_failure_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_text: str) -> RequirementProfile:
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(main, "extract_profile", _boom)
    with pytest.raises(HTTPException) as exc_info:
        await extract_requirements(_pdf_upload("CSE 110"))
    assert exc_info.value.status_code == 502
