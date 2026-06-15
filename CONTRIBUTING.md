# Contributing

The canonical PR lifecycle for this repo. `CLAUDE.md` summarizes it; this file is the source of
truth. The live task board is `docs/EXECUTION.md`.

## One task = one PR

1. **Branch** off the current `main`: `<type>/<short-slug>` — e.g. `feat/profile-data-layer`,
   `chore/api-client`. Type is the conventional-commits type. **No milestone labels** (M4, P1) in
   branch names or PR titles.
2. **Open a draft PR on the first commit**:
   ```bash
   git push -u origin <branch>
   gh pr create --draft --title "<type>: <summary>" --body "<what & why>"
   ```
3. **Work in small commits.** Run the side's gates **between commits** (see below). Commit
   regularly so progress is legible.
4. **Finish**: self-review the full diff, fix anything, make a final commit, then:
   ```bash
   gh pr ready
   ```

## PR titles & commit messages
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- The PR title describes the change for anyone reading the repo — readable, not internal jargon.
- **No model attribution**: no `Co-Authored-By: Claude …` trailers, no "Generated with Claude Code"
  in PR bodies.

## Gates (must pass before marking ready; CI enforces them too)

**Backend** (from `backend/`):
```bash
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest -q
```

**Frontend** (from `frontend/`):
```bash
pnpm lint
pnpm typecheck
pnpm format:check
pnpm build
```
Plus a **manual browser pass** of the affected flow (no frontend unit tests until the user-test
milestone). Start the dev server with the env exported — see the env quirk in `CLAUDE.md`.

## Concurrency
Independent tasks run in **separate git worktrees** so working trees never collide. Each task in
`docs/EXECUTION.md` notes the files it owns; respect single-owner of hotspot files (e.g.
`frontend/app/chat/page.tsx`) to avoid merge conflicts between parallel PRs.
