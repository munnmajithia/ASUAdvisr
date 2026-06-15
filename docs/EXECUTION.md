# Execution Board — MVP completion

The live tactical board. Strategy: [VISION.md](VISION.md); phases: [ROADMAP.md](ROADMAP.md).
Process rules: [CONTRIBUTING.md](../CONTRIBUTING.md).

**How to use this board:** pick the highest-priority task in your lane whose dependencies are
merged, claim it (PR with the suggested title), follow the PR lifecycle in `CONTRIBUTING.md`
(branch → draft PR → gates between commits → self-review → `gh pr ready`). One task = one PR.
Conventional-commit titles; never milestone labels in titles.

## Status (updated 2026-06-15)

The backend MVP is **feature-complete and merged**. A pre-test audit found the remaining work is
almost entirely the **M4 frontend layer** (it doesn't exist yet) plus a few backend correctness
fixes. The fix list below is the path to a testable end-to-end MVP.

**Merged on `main`:** contributor docs/board · requirement-profile extractor
(`llm/requirement_extractor.py`, richer nested JSONB schema — canonical per PR #17) · PDF util
(`pdf/extract.py`) · migrations `0002_requirement_profiles.sql` (parent table + RLS) and
`0003_requirement_profile_jsonb.sql` (JSONB `completed_courses`/`remaining_requirements` columns;
drops 0002's child tables) · `POST /extract-requirements` endpoint (returns the richer shape) · seat
status + open-only filter · instructor names · soft-constraint ranking (`scheduler/rank.py`) · CI
fix · typed frontend API client (`lib/api.ts`) · frontend requirement-profile data layer
(`lib/profile.ts`, JSONB shape) · api-types sync · AuthGate robustness.

## Locked decisions
- **Persistence = stateless backend + frontend-direct Supabase.** Backend extracts and schedules
  only; no user state, no JWT. The frontend persists the *confirmed* profile via the authenticated
  Supabase client; RLS scopes every row to `auth.uid()`.
- **No `Authorization` header on API calls.** The backend verifies no JWT (stateless); per-user
  data is written frontend-direct through the RLS-scoped Supabase client. Do **not** add a bearer
  header to `lib/api.ts` (resolves the old task-5 gate note).
- **Canonical `RequirementProfile`** — the **richer nested** shape produced by
  `llm/requirement_extractor.py`, persisted as JSONB by migration `0003_requirement_profile_jsonb.sql`
  and mirrored by the TS type in `frontend/lib/profile.ts`. (Adopted as canonical by PR #17, which
  deleted the old flat `requirement_profile.py`/`dars_extractor.py` and dropped 0002's child tables.)
  ```jsonc
  {
    "catalog_year": "2023-2024", "major": "Computer Science (BS)",
    "completed_courses": [
      { "course": "CSE 110", "title": "Principles of Programming", "grade": "A",
        "term": "FA23", "credits": 3, "in_progress": false }
    ],
    "remaining_requirements": [
      { "label": "CSE 355", "options": ["CSE 355"], "pick": 1,
        "credits_needed": 3, "note": null },
      { "label": "CSE 412 OR CSE 434 OR CSE 445", "options": ["CSE 412", "CSE 434", "CSE 445"],
        "pick": 1, "credits_needed": null, "note": null },
      { "label": "Upper Division Technical Electives", "options": [], "pick": 1,
        "credits_needed": 6, "note": "any CSE 4xx; NOT FROM: CSE 485, 486" }
    ]
  }
  ```
  Every field except `course` (in completed) and `label`/`options`/`pick` (in remaining) is optional.
  `to_requirements()` maps each remaining requirement with **non-empty** `options` to the scheduler's
  `CourseRequirement(course_keys=options, pick=pick)`. Empty-`options` requirements
  (wildcards/open-electives/hour-based needs) are **excluded** from scheduling and surfaced separately
  via `unresolved_requirements()` so the review UI can require concrete `options` before scheduling
  (see B3). Completed courses never become requirements.

## Ownership lanes
- **Backend lane → owned by the active session (claude).** B1–B3 + the local venv fix.
- **Frontend lane → handoff to other instances.** F1–F9. Work in your own clone/worktree.

## Fix tasks (from the 2026-06-15 pre-test audit)

### Backend lane (claude is on these)
| ID | Priority | PR title | Key files / goal | Deps |
|----|----------|----------|------------------|------|
| B1 | P0 | `chore: remove stray duplicate files` | Delete 10 untracked `* 2.*` macOS dups (4 under `backend/src` are linted/typed; also `frontend/lib/*  2.ts`, dup `0002 2.sql`, `* 2.md`). `find . -name '* 2.*' -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/.next/*' -delete`; add `* 2.*` to `.gitignore`. | — |
| ~~B2~~ | — | ~~`refactor: consolidate DARS extractors`~~ | **Resolved by PR #17 — in the opposite direction.** The consolidation kept the *richer* `requirement_extractor.py` (with its `max_tokens` guard and `RuntimeError`-on-no-tool_use guard already in place) as canonical and **deleted** the flat `dars_extractor.py`/`requirement_profile.py`. Migration `0003` made the richer JSONB shape the persisted schema. No further work; row kept for history. | — |
| B3 | P1 | `fix: signal dropped/unsatisfiable requirements from /schedule` | `to_requirements()` already **excludes** empty-`options` remaining requirements (wildcards/open-electives), so none reach `enumerate_schedules` (which returns `[]` for any unsatisfiable req), and `unresolved_requirements()` surfaces them — both shipped with the richer schema. Remaining work: `to_requirements()` shouldn't drop *silently*, and `/schedule` should report which requirements were unresolved or yielded zero candidates (not just return `[]`). Test: a wildcard-only profile doesn't silently yield `[]`. | — |
| — | P2 | (local, no PR) regenerate `.venv` | `backend/.venv/.../asuadvisr.pth` is malformed (`import _virtualenv` run into the src path). `uv sync --reinstall`. Local-only; gates/CI unaffected. | — |

### Frontend lane (handoff)
| ID | Priority | PR title | Key files / goal | Deps |
|----|----------|----------|------------------|------|
| F1 | P0 | `feat: add extractProfile multipart helper` | `lib/api.ts`: `extractProfile(file): Promise<RequirementProfile>` — `FormData` with key `file` (endpoint param is `Annotated[UploadFile, File()]`). `request()` force-sets JSON content-type, so special-case `FormData` (let the browser set the multipart boundary) or use a dedicated fetch. No auth header. | — |
| F2 | P0 | `feat: requirement-profile data layer` | `lib/profile.ts`: TS `RequirementProfile` (richer JSONB shape above) + `saveProfile`/`loadProfile` via `getBrowserSupabase()` (single `requirement_profiles` row; `completed_courses`/`remaining_requirements` JSONB, `user_id` from session) + `profileToRequirements()` mapping (non-empty `options` → `{course_keys, pick}`). | migration (merged) |
| F3 | P0 | `feat: mandatory editable requirement review UI` | `components/requirement-review.tsx`: editable form over the draft profile. **Must visibly warn on every empty-`options` remaining requirement (wildcard/open-elective — i.e. `unresolved_requirements()`) and require concrete `options`** (else it's excluded and scheduling silently drops it — see B3). Confirm → `saveProfile()` → `/chat`. | F2 |
| F4 | P0 | `feat: DARS upload onboarding page` | `app/onboarding/page.tsx` in `<AuthGate>`: PDF input (reject non-PDF) → `extractProfile(file)` → draft → `<RequirementReview>`. Surface 422 / 502 / backend-down. | F1, F3 |
| F5 | P0 | `feat: drive chat from confirmed profile` | `app/chat/page.tsx`: `loadProfile()` on mount (→ `/onboarding` if none); build requirements from `profileToRequirements()` not the manual picker; confirmed courses read-only + 'edit profile' link. **Sole owner of `chat/page.tsx`** (sequence F8 after). | F2 |
| F6 | P0 | `feat: auth-aware landing page` | Replace `app/page.tsx` (still create-next-app template); update `layout.tsx` metadata to ASUAdvisr. Routing: signed-out → sign-in; signed-in → `loadProfile()` → `/onboarding` or `/chat`. **Sole owner of `layout.tsx`**. | F2 |
| F7 | P1 | `chore: sync api-types with current API` | `lib/api-types.ts`: add `enrl_stat`, `is_open`, `instructors` to `SectionDetail`; add `only_open`, `compact_schedule`, `prefer_time_of_day` to `ApiConstraints`. Prereq for F8. | — |
| F8 | P1 | `feat: enrich results UI` | Shared `ScheduleCard`: Open/Closed badge (`is_open`) + instructor line; confirming step gets only-open toggle + `compact_schedule`/`prefer_time_of_day` controls threaded through `toApiConstraints`. | F7, F5 |
| F9 | P2 | `chore: retire or convert old schedule page` | `app/schedule/page.tsx` is a divergent M2 prototype (no AuthGate). Retire it or convert to the profile-driven path behind AuthGate using the shared `ScheduleCard`. | F5 |

### Frontend dependency DAG
```
F1 ─┐                         ┌─► F3 ─┐
    │                         │       ├─► F4
F2 ─┼─────────────────────────┼─► F5 ─┼─► F8   (F8 also needs F7)
    │                         └─► F6  │
F7 ─┘                                 └─► F9
```
Start-now (no deps): **F1, F2, F7**, and **B1, B2, B3**. Hotspots: `chat/page.tsx` → F5 then F8;
`layout.tsx` → F6 only.

## Closing gate
After the P0 lane lands: full end-to-end manual run — sign in → upload the sanitized DARS
(`backend/tests/fixtures/dars/dars_sanitized.pdf`) → review/edit (resolve empty-`options` requirements) → confirm
→ chat constraints → schedules render (with seats/instructors/ranking once F8 lands) → copy class
numbers. Then M5 (5 ASU CS students; non-code).
