"""Week 0 spike — full-term scrape of ASU Class Search.

Findings so far:
- Public API: https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes
- Auth: requires *some* Authorization header. The string `Authorization: Bearer null`
  is accepted as anonymous (the server's JWT parser apparently treats `null` as a
  no-op principal). No real OAuth flow needed for read-only catalog access.
- Pagination: Elasticsearch-style scrollId. Each page returns up to 200 records.
- Response shape: {classes: [...], aggregations: {...}, scrollId: str, total: {value, relation}}
"""

import hashlib
import json
import os
import sys
import time

import httpx

BASE = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes"
HEADERS = {
    "Authorization": "Bearer null",
    "Accept": "application/json",
    "Origin": "https://catalog.apps.asu.edu",
    "Referer": "https://catalog.apps.asu.edu/",
    "User-Agent": "ASUAdvisr-spike/0.1",
}


def fetch_full_term(client: httpx.Client, subject: str, term: str) -> tuple[list[dict], dict]:
    """Pull every class section for a (subject, term). Returns (records, meta)."""
    records: list[dict] = []
    scroll_id: str | None = None
    page = 0
    timings: list[float] = []
    while True:
        page += 1
        params = {
            "refine": "Y",
            "subject": subject,
            "term": term,
            "campusOrOnlineSelection": "A",
            "pageSize": "200",
        }
        if scroll_id:
            params["scrollId"] = scroll_id
        t0 = time.perf_counter()
        r = client.get(BASE, params=params, headers=HEADERS, timeout=30)
        timings.append(time.perf_counter() - t0)
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("classes", [])
        records.extend(batch)
        total = payload["total"]["value"]
        print(f"  page {page}: +{len(batch)} (running total {len(records)}/{total}) in {timings[-1]:.2f}s")
        scroll_id = payload.get("scrollId")
        if not batch or len(records) >= total:
            break
        if page > 50:
            print("  safety break at page 50")
            break
    meta = {
        "subject": subject,
        "term": term,
        "expected_total": total,
        "fetched_total": len(records),
        "pages": page,
        "per_page_seconds": timings,
        "sum_seconds": sum(timings),
    }
    return records, meta


def fingerprint(records: list[dict]) -> str:
    """Order-independent hash of section identity + key fields."""
    keys = []
    for c in records:
        ident = c.get("SECTIONCLASSNUMBER") or c.get("CLAS", {}).get("classNbr") or ""
        # also include things likely to change between runs we want to ignore
        keys.append(str(ident))
    keys.sort()
    return hashlib.sha256("\n".join(keys).encode()).hexdigest()


def burst_probe(client: httpx.Client, n: int = 20) -> dict:
    """Quick burst to test rate-limit behavior."""
    statuses: list[int] = []
    timings: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        r = client.get(BASE, params={"refine": "Y", "subject": "CSE", "term": "2267", "pageSize": "10", "campusOrOnlineSelection": "A"}, headers=HEADERS, timeout=15)
        timings.append(time.perf_counter() - t0)
        statuses.append(r.status_code)
    return {"statuses": statuses, "p50": sorted(timings)[len(timings)//2], "max": max(timings), "min": min(timings)}


def main() -> int:
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with httpx.Client() as client:
        print("[A] full-term pull #1: CSE Fall 2026 (term=2267)")
        recs1, meta1 = fetch_full_term(client, "CSE", "2267")
        with open(os.path.join(out_dir, "cse_fall26_run1.json"), "w") as f:
            json.dump({"meta": meta1, "records": recs1}, f, indent=2)
        fp1 = fingerprint(recs1)
        print(f"  fingerprint: {fp1[:16]}  total: {meta1['sum_seconds']:.2f}s\n")

        print("[B] full-term pull #2 (idempotency check)")
        recs2, meta2 = fetch_full_term(client, "CSE", "2267")
        fp2 = fingerprint(recs2)
        print(f"  fingerprint: {fp2[:16]}  match: {fp1 == fp2}\n")

        print("[C] burst probe (20 requests, no delay)")
        b = burst_probe(client, n=20)
        ok = sum(1 for s in b["statuses"] if s == 200)
        print(f"  {ok}/20 OK, latencies min={b['min']:.2f} p50={b['p50']:.2f} max={b['max']:.2f}")
        print(f"  status codes: {b['statuses']}\n")

        print("[D] sanity check: a couple other big subjects")
        for subj in ("MAT", "ENG"):
            recs, meta = fetch_full_term(client, subj, "2267")
            print(f"  {subj} Fall26: {meta['fetched_total']} sections in {meta['pages']} pages ({meta['sum_seconds']:.2f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
