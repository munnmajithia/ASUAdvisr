# ASUAdvisr — Working Agreement (read this first)

Conversational course-scheduling MVP for ASU students. The product hypothesis: students prefer
conversational scheduling to MyASU. **Core principle:** LLMs only extract / interpret / converse;
deterministic code validates and generates. Keep that separation — it is load-bearing for trust.

## Orientation
- **`docs/VISION.md`** — strategy, product pillars, the moat.
- **`docs/ROADMAP.md`** — strategic phases and milestone status.
- **`docs/EXECUTION.md`** — the live tactical task board. **Check this before picking up work**: it
  lists every open task, its dependencies, gate, and which files it owns.
- **`CONTRIBUTING.md`** — the PR lifecycle (the canonical source for the rules summarized below).

## Repo layout
- `backend/` — FastAPI + Python 3.12, managed by `uv`. Stateless: extracts and schedules, holds no
  user state. `src/asuadvisr/{api,scraper,scheduler,llm,db,pdf}`.
- `frontend/` — Next.js 16 (App Router) + React 19 + Tailwind v4, managed by `pnpm`.
- `supabase/migrations/` — versioned SQL. Per-user data is RLS-scoped to `auth.uid()`.
- `docs/`, `spike/`, `.github/workflows/`.

## Run & verify
**Backend** (from `backend/`): `uv sync` then
`uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`.

**Frontend** (from `frontend/`): `pnpm install` then
`pnpm lint && pnpm typecheck && pnpm format:check && pnpm build`.
No frontend unit tests until the user-test milestone — the frontend gate is
lint + typecheck + format:check + build **plus a manual browser pass**.

CI (`.github/workflows/ci.yml`) mirrors both on every PR.

### Env quirk (matters for the frontend)
There is a single `.env` at the repo root. The backend reads it via pydantic-settings. The
frontend needs `NEXT_PUBLIC_*` exported into its environment to see them, so run the dev server as:
```bash
cd frontend && set -a && source ../.env && set +a && pnpm dev
```
`.env.example` documents the variables.

## Dev rules (every task follows these — see CONTRIBUTING.md)
- **One task = one PR** on its own branch `<type>/<slug>`.
- The first commit **opens a draft PR**; commit regularly; run the side's gates **between commits**.
- When done: self-review the diff, fix, final commit, mark the PR **ready**.
- **PR titles use conventional commits** (`feat:`/`fix:`/`chore:`/`docs:`/`test:`). **Never** put
  milestone labels (M4, P1, …) in PR titles or branch names — those are internal-docs-only.
- **No model attribution anywhere.** Do not add `Co-Authored-By: Claude …` trailers to commits or
  "Generated with Claude Code" lines to PR bodies. (Some historical commits have them; do not add
  any more.)
