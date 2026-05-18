# ASUAdvisr

Conversational course scheduling platform for Arizona State University students.

The product hypothesis: students prefer conversational scheduling to MyASU's existing flow. This MVP exists to validate that.

**Architectural principle:** LLMs handle extraction, interpretation, and conversation. Deterministic code handles validation and schedule generation.

Build plan and milestone details live in [the planning doc](https://github.com/munnmajithia/ASUAdvisr) (kept locally during development).

## Repo layout

```
ASUAdvisr/
├── backend/       # FastAPI + Python 3.12, managed by uv. src/asuadvisr/{api,scraper,scheduler,llm,db}
├── frontend/      # Next.js (App Router) + Tailwind + TypeScript, managed by pnpm
├── supabase/      # Supabase CLI config + SQL migrations
├── spike/         # Week 0 scraping spike artifacts (read FINDINGS.md first)
├── .github/       # GitHub Actions: CI, scraper cron, daily smoke
└── .env.example   # copy to .env and fill in Supabase + Anthropic keys
```

## Prerequisites

- macOS with Homebrew
- Node ≥ 20 (LTS), Python 3.12
- `brew install uv pnpm supabase/tap/supabase`

## Setup

1. Clone, then `cp .env.example .env` and fill in Supabase URL/keys.
2. Link the Supabase project (one-time): `supabase link --project-ref <YOUR_REF>`
3. Backend: `cd backend && uv sync`
4. Frontend: `cd frontend && pnpm install`
5. (M1.1+) Apply DB migrations: `supabase db push`

## Daily commands

| Task | Command |
|---|---|
| Run backend tests | `cd backend && uv run pytest` |
| Lint + format check (backend) | `cd backend && uv run ruff check && uv run ruff format --check` |
| Typecheck (backend) | `cd backend && uv run mypy` |
| Run frontend dev server | `cd frontend && pnpm dev` |
| Typecheck (frontend) | `cd frontend && pnpm typecheck` |
| Lint (frontend) | `cd frontend && pnpm lint` |
| Format (frontend) | `cd frontend && pnpm format` |
| Run scraper locally (M1.1+) | `cd backend && uv run python -m asuadvisr.scraper.asu_class_search --term 2267 --subject CSE` |

## CI

Three GitHub Actions workflows in `.github/workflows/`:

- **`ci.yml`** — runs on every PR: backend (`ruff` + `mypy` + `pytest`) and frontend (`pnpm lint` + `pnpm typecheck` + `pnpm build`).
- **`scrape.yml`** — cron-scheduled, runs the ASU Class Search scraper and upserts into Supabase.
- **`smoke.yml`** — daily schema-drift check against a pinned fixture.

The scraper needs `SUPABASE_SERVICE_ROLE_KEY` set as a repo secret.
