"""Scraper for the ASU Class Search microservice.

Fetches all class sections for a given subject + term and upserts them into
Supabase.  The `Bearer null` trick discovered in the Week 0 spike gives anonymous
read-only access without OAuth.

Usage (via GitHub Actions or locally):
    uv run python -m asuadvisr.scraper.asu_class_search --subject CSE --term 2267
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

import httpx

from asuadvisr.db.client import get_client, upsert_all
from asuadvisr.scraper.parse import parse_record

logger = logging.getLogger(__name__)

BASE_URL = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes"
HEADERS = {
    "Authorization": "Bearer null",
    "Accept": "application/json",
    "Origin": "https://catalog.apps.asu.edu",
    "Referer": "https://catalog.apps.asu.edu/",
    "User-Agent": "ASUAdvisr/0.1 (+github.com/munnmajithia/ASUAdvisr)",
}
PAGE_SIZE = 200
MAX_PAGES = 50  # safety cap
MAX_RETRIES = 4
RETRY_BACKOFF = 2.0  # seconds; doubles on each retry


def _fetch_page(
    client: httpx.Client,
    subject: str,
    term: str,
    scroll_id: str | None,
) -> dict[str, Any]:
    """Fetch one page with exponential backoff on transient failures."""
    params: dict[str, str] = {
        "refine": "Y",
        "subject": subject,
        "term": term,
        "campusOrOnlineSelection": "A",
        "pageSize": str(PAGE_SIZE),
    }
    if scroll_id:
        params["scrollId"] = scroll_id

    delay = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()  # type: ignore[no-any-return]
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if attempt == MAX_RETRIES:
                raise
            logger.warning("attempt %d failed (%s); retrying in %.1fs", attempt, exc, delay)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def fetch_all(subject: str, term: str) -> list[dict[str, Any]]:
    """Return all raw section records for (subject, term)."""
    records: list[dict[str, Any]] = []
    scroll_id: str | None = None
    expected: int | None = None

    with httpx.Client() as client:
        for page in range(1, MAX_PAGES + 1):
            t0 = time.perf_counter()
            payload = _fetch_page(client, subject, term, scroll_id)
            elapsed = time.perf_counter() - t0

            batch: list[dict[str, Any]] = payload.get("classes", [])
            if expected is None:
                expected = payload.get("total", {}).get("value", 0)
            records.extend(batch)
            scroll_id = payload.get("scrollId")

            logger.info(
                "page %d: +%d → %d/%d (%.2fs)",
                page,
                len(batch),
                len(records),
                expected,
                elapsed,
            )

            if not batch or len(records) >= (expected or 0):
                break
        else:
            logger.warning("hit MAX_PAGES=%d safety cap", MAX_PAGES)

    logger.info("fetched %d sections for %s term=%s", len(records), subject, term)
    return records


def run(subject: str, term: str) -> None:
    """Fetch and upsert all sections for (subject, term)."""
    records = fetch_all(subject, term)
    client = get_client()

    ok = 0
    errors = 0
    for raw in records:
        try:
            parsed = parse_record(raw)
            upsert_all(client, parsed)
            ok += 1
        except Exception:
            class_nbr = raw.get("CLAS", {}).get("CLASSNBR", "?")
            logger.exception("failed to upsert section %s", class_nbr)
            errors += 1

    logger.info("done: %d upserted, %d errors", ok, errors)
    if errors:
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape ASU Class Search into Supabase")
    p.add_argument("--subject", default="CSE", help="Subject code (e.g. CSE)")
    p.add_argument("--term", default="2267", help="ASU STRM code (e.g. 2267 = Fall 2026)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    run(args.subject, args.term)
