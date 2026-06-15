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

**Merged on `main`:** contributor docs/board · requirement-profile contract (`llm/requirement_profile.py`)
· PDF util (`pdf/extract.py`) · migration `0002_requirement_profiles.sql` (RLS) · DARS extractor
(`llm/dars_extractor.py`) · `POST /extract-requirements` endpoint · seat status + open-only filter
· instructor names · soft-constraint ranking (`scheduler/rank.py`) · CI fix · typed frontend API
client (`lib/api.ts`) · AuthGate robustness.

## Locked decisions
- **Persistence = stateless backend + frontend-direct Supabase.** Backend extracts and schedules
  only; no user state, no JWT. The frontend persists the *confirmed* profile via the authenticated
  Supabase client; RLS scopes every row to `auth.uid()`.
- **No `Authorization` header on API calls.** The backend verifies no JWT (stateless); per-user
  data is written frontend-direct through the RLS-scoped Supabase client. Do **not** add a bearer
  header to `lib/api.ts` (resolves the old task-5 gate note).
- **Canonical `RequirementProfile`** — the **wired** shape (in `llm/requirement_profile.py`, matched
  by migration 0002 and the planned TS type):
  ```jsonc
  {
    "catalog_year": "2024-2025", "major": "Computer Science",
    "completed_courses": ["CSE 110", "MAT 265"],
    "required_courses_remaining": ["CSE 310", "CSE 355"],
    "choice_groups": [{ "name": "CS Electives", "pick": 1, "course_keys": ["CSE 412", "CSE 420"] }]
  }
  ```
  Map to the scheduler's `{course_keys, pick}`: required → `{course_keys:[c], pick:1}`; choice group
  with keys → `{course_keys, pick}`; completed + keyless-filter-only groups excluded. (The richer
  `requirement_extractor.py` schema is dead/unwired and is being retired — see B2.)

## Ownership lanes
- **Backend lane → owned by the active session (claude).** B1–B3 + the local venv fix.
- **Frontend lane → handoff to other instances.** F1–F9. Work in your own clone/worktree.

## Fix tasks (from the 2026-06-15 pre-test audit)

### Backend lane (claude is on these)
| ID | Priority | PR title | Key files / goal | Deps |
|----|----------|----------|------------------|------|
| B1 | P0 | `chore: remove stray duplicate files` | Delete 10 untracked `* 2.*` macOS dups (4 under `backend/src` are linted/typed; also `frontend/lib/*  2.ts`, dup `0002 2.sql`, `* 2.md`). `find . -name '* 2.*' -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/.next/*' -delete`; add `* 2.*` to `.gitignore`. | — |
| B2 | P1 | `refactor: consolidate DARS extractors` | Keep the wired `dars_extractor.py`/`requirement_profile.py`. Port the dead `requirement_extractor.py`'s guards (raise on `stop_reason=='max_tokens'`; replace bare `next(...)` over tool-use blocks — **throws unhandled `StopIteration` on an LLM refusal** — with a clear `RuntimeError`) and its uAchieve/DARS prompt into `dars_extractor.py`; migrate its real-DARS fixture test; then delete `requirement_extractor.py` + its test. | — |
| B3 | P1 | `fix: guard scheduler against empty-options requirements` | `to_requirements()` must report dropped keyless groups (not skip silently); never let an empty-`course_keys` `CourseRequirement` reach `enumerate_schedules` (which returns `[]` for any unsatisfiable req); `/schedule` should signal which reqs yielded zero candidates. Test: keyless/wildcard-only profile doesn't silently yield `[]`. | — |
| — | P2 | (local, no PR) regenerate `.venv` | `backend/.venv/.../asuadvisr.pth` is malformed (`import _virtualenv` run into the src path). `uv sync --reinstall`. Local-only; gates/CI unaffected. | — |

### Frontend lane (handoff)
| ID | Priority | PR title | Key files / goal | Deps |
|----|----------|----------|------------------|------|
| F1 | P0 | `feat: add extractProfile multipart helper` | `lib/api.ts`: `extractProfile(file): Promise<RequirementProfile>` — `FormData` with key `file` (endpoint param is `Annotated[UploadFile, File()]`). `request()` force-sets JSON content-type, so special-case `FormData` (let the browser set the multipart boundary) or use a dedicated fetch. No auth header. | — |
| F2 | P0 | `feat: requirement-profile data layer` | `lib/profile.ts`: TS `RequirementProfile` (wired shape above) + `saveProfile`/`loadProfile` via `getBrowserSupabase()` (parent + 4 child tables, `user_id` from session) + `profileToRequirements()` mapping. | migration (merged) |
| F3 | P0 | `feat: mandatory editable requirement review UI` | `components/requirement-review.tsx`: editable form over the draft profile. **Must visibly warn on every keyless / filter-only choice group and require concrete `course_keys`** (else scheduling silently returns zero — see B3). Confirm → `saveProfile()` → `/chat`. | F2 |
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
(`backend/tests/fixtures/dars/dars_sanitized.pdf`) → review/edit (resolve keyless groups) → confirm
→ chat constraints → schedules render (with seats/instructors/ranking once F8 lands) → copy class
numbers. Then M5 (5 ASU CS students; non-code).
