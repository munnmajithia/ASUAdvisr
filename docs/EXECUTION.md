# Execution Board — MVP completion

The live tactical board for finishing the MVP. Strategy lives in [VISION.md](VISION.md); phases in
[ROADMAP.md](ROADMAP.md). Process rules: [CONTRIBUTING.md](../CONTRIBUTING.md).

**How to use this board:** pick the lowest-numbered task whose dependencies are merged, follow the
PR lifecycle in `CONTRIBUTING.md`, and check it off when its PR is marked ready. Internally we still
think in milestones (M4 = requirement extraction); PR titles never use those labels.

## What's done
M1.0 scaffold · M1.1 data foundation · M2 scheduler+API+UI · M3 NL constraint parser + chat UI +
magic-link auth. Remaining MVP work = M4 (DARS extraction + review) + integration glue + selected
low-hanging add-ons.

## Locked decisions
- **Persistence = stateless backend + frontend-direct Supabase.** Backend extracts and schedules
  only; no user state, no JWT verification. The frontend persists the *confirmed* profile via the
  authenticated Supabase client; RLS scopes every row to `auth.uid()`.
- **Canonical `RequirementProfile`** (one shape across Python model, SQL tables, TS type):
  ```jsonc
  {
    "catalog_year": "2024-2025",
    "major": "Computer Science",
    "completed_courses": ["CSE 110", "MAT 265"],
    "required_courses_remaining": ["CSE 310", "CSE 355"],
    "choice_groups": [{ "name": "CS Electives", "pick": 1, "course_keys": ["CSE 412", "CSE 420"] }]
  }
  ```
  Course keys normalize to `"SUBJECT CATALOG_NBR"`. Map to the scheduler's `{course_keys, pick}`:
  required course → `{course_keys:[c], pick:1}`; choice group → `{course_keys, pick}`; completed
  excluded. The executing mapping is in TypeScript (frontend calls `/schedule`); a mirrored,
  unit-tested Python helper documents the contract.
- **Add-ons in scope:** seat status + open-only filter, soft-constraint ranking, instructor names.
  **Calendar (.ics) export is deferred.**

## Dependency DAG
```
            ┌─ #1 contract ──┬──────────────► #6 extractor ──► #8 extract-endpoint
 Setup ─┬───┤  #2 pdf-util ──┘                    ▲
        │   ├─ #3 migration ─────────────┐        │
        │   ├─ #4 dars-fixture ──────────┴── feeds tests
        │   └─ #5 api-client ─┬─► #7 data-layer ─┬─► #10 review-ui ─┐
        │                     │                  ├─► #11 landing ───┼─► #12 chat-from-profile ─► #16 enrich-ui
        │                     └─► #9 upload-page ─┘ (needs #8)       ┘
        └─ #13 seats · #14 instructors · #15 ranking  (backend-only, interleave) ──► #16
```

## Waves
- **W1 (parallel):** #1, #2, #3, #4, #5 — start as soon as Setup merges.
- **W2 (parallel):** #6, #7, and add-ons #13, #14, #15 interleave (backend-only).
- **W3 (parallel):** #8, #9, #10, #11.
- **W4:** #12 (chat convergence).
- **W5:** #16 (consolidated results UI for the add-ons).

## Hotspot single-owner rule
- `frontend/app/layout.tsx` → #11 only.
- `frontend/app/chat/page.tsx` → #12, then #16 (sequence #16 after #12).
- `SectionDetail` in `backend/src/asuadvisr/api/main.py` → #8 adds it; #13 and #14 extend it (rebase
  those two against each other).
- `frontend/lib/api.ts` / `frontend/lib/types.ts` → created by #5, appended by #9.

## Tasks

### Core flow
| # | PR title | Goal (key files) | Deps | Gate + tests |
|---|---|---|---|---|
| 1 | `feat: add requirement profile contract` | `backend/src/asuadvisr/llm/requirement_profile.py`: Pydantic `RequirementProfile` + `ChoiceGroup` (`choose`/`pick` alias), `to_requirements()` → `list[CourseRequirement]`, key normalization. | — | mypy; `test_requirement_profile.py`: defaults, alias, required→reqs, group→reqs, normalization. |
| 2 | `feat: add PDF text-extraction utility` | `backend/src/asuadvisr/pdf/extract.py`: `extract_text_from_bytes`, `extract_text_from_path`, `PdfExtractionError`. Wraps PyMuPDF. | — | `test_pdf_extract.py`: text from sample PDF; raises on empty/garbage; bytes==path. |
| 3 | `feat: add requirement profile tables with RLS` | `supabase/migrations/0002_requirement_profiles.sql`: profile + 4 child tables; RLS `USING/WITH CHECK (auth.uid() = user_id)`; child tables via `EXISTS` on parent; indexes. | — (sync shape w/ #1) | `supabase db reset` applies; user A's row invisible to user B (manual check). |
| 4 | `test: add sanitized DARS fixture` | `backend/tests/fixtures/dars_sample.txt` + synthetic `dars_sample.pdf` + `fixtures/README.md`; `.gitignore` real-DARS patterns; optional env-driven `test_fixture_has_no_pii`. Never commit real DARS. | — | manual no-PII review; readable by #2. |
| 5 | `chore: add shared API client with auth token` | `frontend/lib/api.ts` (+ `lib/types.ts`): `API_BASE`, `apiFetch<T>` with `!res.ok` throw + `Authorization: Bearer <token>`; typed `getCourses/parseConstraints/postSchedule`; move shared interfaces. | — | lint+typecheck+build; `/schedule` still works; request carries auth header when signed in. |
| 6 | `feat: add DARS requirement extractor` | `backend/src/asuadvisr/llm/dars_extractor.py`: `extract_profile(text, client=None)`. Clone of `constraint_parser.py` (Haiku 4.5, forced tool_use, caching, `max_tokens≈2048`). | 1, 4 | mypy; `test_dars_extractor.py` (mock client): completed/required/choice-group alias, empty→default, tool forced, text forwarded. |
| 7 | `feat: requirement-profile data layer` | `frontend/lib/profile.ts`: TS `RequirementProfile`, `loadProfile`/`saveProfile` via authed Supabase (sets `user_id`), `profileToRequirements`. | 5, (3 soft) | lint+typecheck+build; save→load round-trip; eyeball mapping. |
| 8 | `feat: extract requirement profile from DARS PDF` | `api/main.py`: `POST /extract-requirements` (multipart) → text (422 on `PdfExtractionError`) → `extract_profile` (502 on failure) → `RequirementProfile`. Stateless. | 1, 2, 6 | `test_api.py` (TestClient, monkeypatched extractor): 200 / 422 / 502. |
| 9 | `feat: DARS PDF upload page` | `frontend/app/onboarding/page.tsx` in `<AuthGate>`: PDF input → `extractProfile(file)` (added to `lib/api.ts`) → draft → review UI. | 5, (8 for live) | lint+typecheck+build; upload → draft renders; non-PDF rejected; backend-down error. |
| 10 | `feat: mandatory editable requirement review UI` | `frontend/components/requirement-review.tsx`: editable form over the draft; "Confirm" → `saveProfile()` → route to `/chat`. | 7 | lint+typecheck+build; edit every field; add/remove group; confirm persists across reload. |
| 11 | `feat: auth-aware landing page` | replace `frontend/app/page.tsx`; update `layout.tsx` metadata. Routing: signed-out→sign-in; no-profile→`/onboarding`; has-profile→`/chat`. | 7 | lint+typecheck+build; all three routing branches; no boilerplate left. |
| 12 | `feat: drive chat scheduling from confirmed profile` | `frontend/app/chat/page.tsx`: replace manual picker with `loadProfile()` (redirect to onboarding if none) → request from `profileToRequirements`. Keep parse/confirm/results. | 7, 9, 10, 11 | lint+typecheck+build; full end-to-end chain. |

### Add-ons (interleaved)
| # | PR title | Goal (key files) | Deps | Gate + tests |
|---|---|---|---|---|
| 13 | `feat: surface section seat status with open-only filter` | `enrl_stat` (+ seats) into `SectionDetail` (`api/main.py`); `only_open` in `ConstraintsIn`/`ScheduleConstraints` + filter in `scheduler/constraints.py`. | — (rebase vs #14 on `SectionDetail`) | mypy; `test_scheduler.py`: only-open reduces results; `test_api.py`: status present. |
| 14 | `feat: add instructor names to scheduler output` | `instructors: list[str]` on `SectionNode`; parse in `load_sections_from_fixture` reusing `scraper/parse.py:_parse_instructors` decode; surface in `SectionDetail`. | — (rebase vs #13 on `SectionDetail`) | mypy; `test_scheduler.py`: known fixture section → expected instructor(s). |
| 15 | `feat: rank schedules by soft constraints` | soft prefs (`compact_schedule`, `prefer_time_of_day`) in `constraint_parser.py` + `ParsedConstraints`; `scheduler/rank.py` scorer; `enumerate_schedules` collects to internal cap within timeout, ranks, returns top `max_results`. | — (independent files) | mypy; `test_rank.py`: compact beats spread, time-of-day order; parser extracts soft prefs; timeout/cap respected. |
| 16 | `feat: enrich schedule UI with seats, instructors, and preference controls` | `chat/page.tsx` + shared `ScheduleCard`: Open/Closed badge + instructor names on cards; only-open toggle + soft-pref controls in the confirming step. | 12, 13, 14, 15 | lint+typecheck+build; badges/instructors render; open-only filters; soft prefs reorder. |

## Internal milestone → PR title mapping
| Internal | Readable PR title(s) |
|---|---|
| Process/docs | `docs: add contributor workflow and execution board` |
| M4 contract/schema | `feat: add requirement profile contract` · `feat: add requirement profile tables with RLS` |
| M4 extraction | `feat: add PDF text-extraction utility` · `feat: add DARS requirement extractor` · `feat: extract requirement profile from DARS PDF` |
| M4 review/onboarding | `feat: DARS PDF upload page` · `feat: mandatory editable requirement review UI` |
| Integration glue | `chore: add shared API client with auth token` · `feat: requirement-profile data layer` · `feat: auth-aware landing page` · `feat: drive chat scheduling from confirmed profile` |
| Add-ons | `feat: surface section seat status with open-only filter` · `feat: add instructor names to scheduler output` · `feat: rank schedules by soft constraints` · `feat: enrich schedule UI with seats, instructors, and preference controls` |
| M5 | user test (non-code) |
