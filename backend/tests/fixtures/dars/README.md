# DARS fixture (M4 requirement extraction)

Test input for the degree-audit extraction pipeline
(`asuadvisr.llm.requirement_extractor`). The source is a **real ASU
uAchieve / CollegeSource "Full Requirements Degree Audit"** for a BS Computer
Science student (Tempe, 2023–24 catalog) — i.e. ASU's current DARS.

## Files

| File | Committed? | What |
|---|---|---|
| `dars_self.pdf` | **No — gitignored** | The real audit. Contains student PII. |
| `dars_self.raw.txt` | **No — gitignored** | Raw `extract_text` dump of the real PDF (PII). |
| `dars_sanitized.pdf` | Yes | PII-free PDF, regenerated from redacted text. The fixture tests load this. |
| `dars_sanitized.txt` | Yes | Text PyMuPDF extracts from `dars_sanitized.pdf` — human-readable reference + regression lock. |

`.gitignore` ignores **every** PDF in this directory by default and allows only
`dars_sanitized.pdf`, so a carelessly-dropped real audit can't be committed.

## PII handling

`scripts/build_dars_fixture.py` redacts: student name → `Test Student`,
student ID → `0000000000`, and the audit-URL session token → `…REDACTED`. The
sanitized PDF is **rebuilt from the redacted text** (not edited in place), so no
original objects, metadata, or hidden layers survive. The script refuses to
write if any known PII string remains in the text or the output PDF bytes; the
test suite re-checks this independently.

## Regenerating

After dropping a fresh `dars_self.pdf` here (or editing redaction rules):

```bash
cd backend && uv run python scripts/build_dars_fixture.py
```

If PyMuPDF's extraction output changes (e.g. a version bump),
`test_matches_committed_text` fails — rerun the script to refresh both files.

## Structure notes (for the LLM extraction stage)

The text linearises top-to-bottom. The shapes the extractor must handle:

- **Header** — `Computer Science, Tempe, 1996/Online, 20231 For 23-24 CATALOG`,
  `BS COMPUTER SCIENCE`, `Program Code ES CSE BS`, `Catalog Year Fall 2023`.
  Top-of-audit status line: `>>>>> AT LEAST ONE REQUIREMENT HAS NOT BEEN SATISFIED`.
- **Course block** — one course is a run of consecutive lines:
  `TERM` (e.g. `SU26`) / `[M|W|D] SUBJ NUM` (e.g. `M CSE 301`) / `HOURS`
  (`3.00`) / `GRADE` / *optional flag* (`>R` repeat, `>>` in progress) / `TITLE`.
- **Grades / status tokens** — real grades (`A+`…`E`), `NR` = in progress
  (Summer 26 courses), `AP` = test credit, `*` = processed repeat/duplicate,
  `EU*` = failed-and-processed.
- **Requirement sections** — a requirement names itself (`CSE 355: 3 hours, C
  minimum`, `Computer Science Upper Division: 31 hours`) then carries a status:
  `NEEDS: 3.00 HOURS`, `X.00 Hours Earned`, `IN-PROG>`, `EARNED:`, or `IP`.
- **Choice / wildcard / exclusion** — `CSE 412 OR CSE 434 OR CSE 445`,
  `COURSE LIST: CSE 4` (means CSE 4xx), and `-> NOT FROM: …` exclusion lists.
- **Redundancy** — a course recurs across many sections (its requirement, the
  general-studies tally, the major-GPA list). Dedupe to a distinct completed set.
- **Repeats** — e.g. CSE 360 appears failed (`FA25 … D`) and again in progress
  (`SU26 … NR`); CSE 301 multiple times. The latest/best attempt is what counts.
- **End sentinel** — `************************ END OF ANALYSIS ************************`.

This single audit is one college's format; the plan expects ~60–70% raw
extraction accuracy across colleges, with the editable review UI closing the gap.
