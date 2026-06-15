# ASUAdvisr — Roadmap

Execution sequencing for the vision in [VISION.md](VISION.md). Milestones are gated on
quality, not calendar dates. The one timing anchor: user testing is only meaningful during a
registration window.

This file is the **strategic** view. The **live tactical board** — every open task with its
dependencies, gate, and tests — is [EXECUTION.md](EXECUTION.md).

## Status (updated 2026-06-12)

| Milestone | State |
|---|---|
| Week 0 — scraping spike | ✅ Done — green-light (`spike/FINDINGS.md`) |
| M1.0 — repo scaffold | ✅ Done |
| M1.1 — data foundation (schema, scraper, parser) | ✅ Done |
| M2 — deterministic scheduler + API + schedule UI | ✅ Done |
| M3 — constraint parser + chat UI + magic-link auth | ✅ Done |
| M4 — DARS extraction + review + integration | 🔶 In progress — see [EXECUTION.md](EXECUTION.md) |
| M5 — user test | ⬜ Not started |

## MVP milestones (M3–M5)

### M3 — Conversational constraints ✅
Signed-in user chats "12–15 credits, no Friday, nothing before 10am" → constraints parse → valid
schedules render. Done (magic-link auth committed in `e145fa2`).

### M4 — Requirement extraction + end-to-end flow
DARS + major map PDF upload → PyMuPDF text extraction → LLM → `RequirementProfile` JSON →
**mandatory editable review UI** → confirmed profile feeds the scheduler, plus the glue that wires
upload → review → chat → schedule into one flow. Extraction is draft data, not truth; expect
60–70% raw accuracy and let the review UI close the gap. Scope now also includes three low-hanging
add-ons pulled forward from P1 (seat status + open-only filter, soft-constraint ranking, instructor
names); calendar export stays in P1.
**Gate:** a real CSE DARS PDF extracts ≥80% of required courses; review UI fixes the rest; the full
flow runs end-to-end. Task-level breakdown in [EXECUTION.md](EXECUTION.md).

### M5 — User test
5 real ASU CS students run the full flow unaided.
**Window:** Spring 2027 registration (Oct–Nov 2026) — the next moment students genuinely need
scheduling. No artificial deadline before it; don't miss it either.
**Gate:** ≥3 of 5 complete onboarding → schedule → export in one session and prefer it to MyASU.

## Post-MVP phases (P1–P4)

Built only after M5 gives signal. Each phase gates the next.

### P1 — Scheduling depth
Restores the remaining MVP scope cuts to make the student wedge sharp: schedule lock + regenerate,
calendar (.ics) export, prerequisite validation against completed courses, all ASU undergraduate
majors. (Soft-constraint ranking, seat status, and instructor names were pulled forward into M4.)
**Gate:** a non-CSE student can use the product unaided.

### P2 — Data moats
Seat-fill history → seat-risk scoring ("this section fills in 3 days"). Professor intelligence
(RateMyProfessor, grade distributions) as ranking signals.
**Gate:** seat-risk scores backtest accurately against a real registration cycle.

### P3 — Academic intelligence
Prerequisite graph, multi-semester planning, graduation forecasting, bottleneck analysis.
**Gate:** a sophomore can generate a credible path-to-graduation plan.

### P4 — Institutional pilot (B2B)
Advisor dashboard over anonymized/consented student data; pitch built from P1–P3 adoption and
accuracy metrics; approach ASU advising.
**Gate:** one advising-department conversation converts to a pilot.

### Why this order
P1 drives student adoption → adoption generates P2's data → P2 + P3 are the live demo that
makes P4's pitch credible. P2 precedes P3 because longitudinal seat data **compounds with
time** — every registration cycle not captured is lost forever; multi-semester planning can be
built whenever.

## Historical reference

The detailed M1–M5 build plan (stack decisions, scope cuts, gotchas, verification tables) was
developed in the local planning doc and is summarized here; milestone-level detail beyond M5
close-out lives in this file going forward.
