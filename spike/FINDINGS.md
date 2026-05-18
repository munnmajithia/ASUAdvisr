# Week 0 Spike — ASU Class Search Scraping Feasibility

**Date**: 2026-05-17
**Verdict**: ✅ **GREEN-LIGHT** — proceed to M1 (Data Foundation)

## TL;DR

ASU Class Search exposes a public JSON microservice that returns up to 200 sections per request and paginates with an Elasticsearch `scrollId`. A full CSE Fall 2026 pull (283 sections) completes in ~1 second across 2 requests. No rate limiting was observed on a 20-request burst. The API accepts the literal `Authorization: Bearer null` as an anonymous token — no real OAuth flow is needed for read-only catalog data.

## API details

| | |
|---|---|
| **Base URL** | `https://eadvs-cscc-catalog-api.apps.asu.edu` |
| **Search classes** | `GET /catalog-microservices/api/v1/search/classes` |
| **Search courses** | `GET /catalog-microservices/api/v1/search/courses` |
| **Other endpoints** | `/search/terms`, `/search/subjects`, `/search/appsettings` (all GET) |
| **Auth required** | yes — `Authorization` header must be present |
| **Anonymous token** | the literal string `null` works: `Authorization: Bearer null` (a quirk of the server's JWT parser) |
| **Origin requirement** | none — no CORS-style server-side enforcement |

### Key query params

| Param | Example | Notes |
|---|---|---|
| `refine` | `Y` | always present in real SPA calls |
| `subject` | `CSE` | subject code |
| `term` | `2267` | ASU strm code; 2=century-prefix, last-two-digits of year, then 1=Spring, 4=Summer, 7=Fall |
| `campusOrOnlineSelection` | `A` | A=all, others map to specific campuses |
| `pageSize` | `200` | max appears to be 200; smaller values are ignored, you still get up to 200 |
| `scrollId` | (opaque) | from previous response; used to fetch next page |

### Response shape (top level)

```json
{
  "classes": [ /* up to 200 section objects */ ],
  "aggregations": { "LOCATION": {...}, "COLLEGE": {...} },
  "scrollId": "FGluY2x1ZGVfY29udGV4dF91dWlkD...",
  "total": { "value": 283, "relation": "eq" }
}
```

### Section object — fields relevant to MVP

Each section has a top-level summary plus a `CLAS` nested dict with the raw PeopleSoft fields:

| MVP need | Field path |
|---|---|
| Course code | `SUBJECTNUMBER` ("CSE 100"); also `CLAS.SUBJECT` + `CLAS.CATALOGNBR` |
| Class number (for enrollment) | `CLAS.CLASSNBR` ("63628") |
| Section number | `CLAS.CLASSSECTION` ("2202") |
| Compact identifier | `SECTIONCLASSNUMBER` ("2202-(63628)") |
| Title | `CLAS.COURSETITLELONG` / `CLAS.TITLE` |
| Description | `CLAS.CLASSDESCR` |
| Credits | `CLAS.UNITSMINIMUM` / `CLAS.UNITSMAXIMUM` / `CLAS.UNITSRANGE` (⚠️ NOT `HOURS` — that's contact hours, not credit hours) |
| Days | `CLAS.MON` / `CLAS.TUES` / `CLAS.WED` / `CLAS.THURS` / `CLAS.FRI` / `CLAS.SAT` / `CLAS.SUN` ("Y"/"N") |
| Meeting times | `CLAS.STARTTIMES` / `CLAS.ENDTIMES` / `CLAS.MEETINGDATES` (lists — sections can have multiple meeting patterns) |
| Campus | `CLAS.CAMPUS` ("TEMPE"/"DTPHX"/etc.); also `CLAS.LOCATION` ("ASUONLINE" for online) |
| Modality | `CLAS.INSTRUCTIONMODE` ("OL"=online, "P"=in-person, "ICOURSE"=iCourse, etc.) |
| Session | `CLAS.SESSIONCODE` ("A"/"B"/"C") |
| Seats | `CLAS.ENRLCAP` / `CLAS.ENRLTOT` / `seatInfo` |
| Waitlist | `CLAS.WAITCAP` / `CLAS.WAITTOT` |
| Open/closed | `CLAS.ENRLSTAT` ("O"=open) |
| Instructor | `CLAS.INSTRUCTORSLASTNAMELIST` / `CLAS.INSTRUCTORSFIRSTNAMELIST` |
| Gen studies | `GSGOLD` (new gen-studies code) / `GSMAROON` (legacy) / `CLAS.RQMNTDESIGNTN` |
| Term | `CLAS.STRM` ("2267") |
| Lab+lecture coupling | **`CLAS.ASSOCIATEDCLASS`** — sections sharing this value form a coupling group; `SSR` / `SSRCOMPONENT` / `COMPONENTPRIMARY` describe component types ("LEC"/"LAB"/"DIS") |
| Cross-listing | `CLAS.SCTNCOMBINEDID` (empty if not cross-listed) |
| Notes | `NOTES` (top-level) — plain text |
| Has syllabus | `HASSYLLABUS` (bool) |

### What's NOT in the search response (probably needs the detail page)

- Prerequisite text
- Fee codes
- Course description (long-form)
- Reserved-seat info

These can be deferred to M2 or pulled lazily per-section.

## Performance

| Test | Result |
|---|---|
| Full CSE Fall 2026 pull (283 sections, 2 pages) | **1.02s** total |
| Idempotency — two consecutive full pulls | fingerprints match (same `CLASSNBR` set) |
| 20-request burst with no delay | **20/20 OK**, p50=0.40s, max=0.98s |
| MAT Fall 2026 (477 sections, 3 pages) | 1.26s |
| ENG Fall 2026 (879 sections, 5 pages) | 2.51s |

Extrapolation: ASU has ~150 undergraduate subjects. At average ~1.5s/subject sequentially, a full-term scrape is ≈ **4 minutes**. With light concurrency (10x), seconds. **Well under the 30-min green-light threshold.**

## Risks / footnotes

1. **`Bearer null` works today; this is fragile.** A future ASU JWT validator upgrade could close this. Mitigation: if it breaks, fall back to the Playwright passive-OAuth flow (sketched in earlier version of the spike script — Playwright can run the SPA, then we capture a real token).
2. **`pageSize` cap.** Asking for `pageSize=10` returned 200 records. The server ignores small page sizes. Inconsequential — we want 200.
3. **`HOURS` ≠ credit hours.** Use `UNITSMINIMUM`/`UNITSMAXIMUM`. Don't be fooled.
4. **Section detail page not yet validated.** Prereqs and fees may need a second request per section. Decide in M1 whether to pull eagerly.
5. **Schema stability.** No version skew observed, but the `/api/v1/` prefix is reassuring. Daily smoke test (per plan M1) should assert field presence on a known-good section.

## Files in this spike

- `probe_classes.py` — throwaway hybrid script (Playwright + httpx). The final implementation should use httpx-only with `Bearer null`, and only fall back to Playwright if anonymous access breaks.
- `cse_fall26_run1.json` — full CSE Fall 2026 pull, all 283 sections, with run metadata
- `cse_fall26_page1.json`, `cse_fall26_page1_run2.json` — earlier single-page captures (can delete)

## Recommendation — proceed to M1

The scraper for M1 can be a simple `httpx`-based pager. No browser automation needed. No rate-limit avoidance needed beyond reasonable courtesy (sleep between subjects). Schema modeling in the DB should use the field names documented above, with `ASSOCIATEDCLASS` as the section-group key from day one.

The next concrete steps:
1. Create Supabase project + draft `schema.sql` modeling `terms`, `courses`, `sections`, `meeting_times`, `instructors`, `section_groups` (from ASSOCIATEDCLASS).
2. Promote `probe_classes.py` into `backend/scraper/asu_class_search.py` with retry/logging/upsert logic.
3. Pick a small fixture (a known CSE 110 lecture+lab pair) and write the daily smoke-test assertion against it.
