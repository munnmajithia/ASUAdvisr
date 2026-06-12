# ASUAdvisr — Product Vision

**One-liner:** An AI academic planning layer that sits on top of university scheduling systems.

## The MVP hypothesis

ASU students prefer conversational scheduling over MyASU's existing workflow.

The MVP exists to validate that — not to ship a finished product. It is validated when ~5 real
ASU CS students can go **upload DARS → review extracted requirements → express preferences in
chat → generate schedules → export class numbers** faster than they can do the same in MyASU,
and say they'd use it again.

## Core philosophy

**LLMs only extract, interpret, and converse. Deterministic code validates and generates.**

The LLM never decides whether a schedule is valid, never resolves a time conflict, and never
picks sections. This separation is load-bearing for:

- **Reliability** — schedule generation can't hallucinate.
- **Explainability** — every schedule can be traced to explicit constraints and section data.
- **Institutional trust** — a university buyer can audit the deterministic core. This is the
  trust story behind the long-term B2B direction.
- **Debugging** — extraction errors and scheduling errors are different failure domains.

A second principle follows from it: **extraction is draft data, not truth.** Everything an LLM
extracts (DARS, major maps, constraints) passes through a user-editable review step before the
deterministic core consumes it.

## The complete product

Four pillars, beyond the MVP:

### 1. Academic intelligence
Prerequisite-graph reasoning, multi-semester planning, graduation forecasting, bottleneck
analysis ("this course gates 4 others — take it now"), failure-recovery planning ("if you drop
CSE 310, here's the new path").

### 2. Enrollment risk modeling
Historical seat-fill-speed prediction, high-demand section detection, seat-risk scoring,
alternate-schedule recommendations. Built on longitudinal seat data the scraper cron is already
capturing — this data compounds with every registration cycle and cannot be backfilled.

### 3. Professor intelligence
RateMyProfessor integration, historical grade distributions, instructor preference weighting as
ranking signals in schedule generation.

### 4. Institutional product
Advisor dashboards, student-risk analysis, degree-progress analytics, department-level planning
tools. **This is the B2B sellable.**

## Strategy

**Student-led wedge → data accumulation → institutional sale.**

1. Students adopt because semester scheduling is genuinely painful and conversational planning
   is faster.
2. Usage accumulates requirement profiles, constraint patterns, and demand signals that no
   outside vendor has.
3. ASU advising (then other universities) is approached with proven student adoption and data
   the institution itself doesn't surface.

## The moat

The moat is **not** schedule generation — constraint solvers are commodities. The moat is:

- Academic state understanding (what a student has done, needs, and can take)
- Requirement modeling (DARS/major-map structure as queryable data)
- Constraint reasoning (natural language → correct structured constraints)
- Conversational planning UX
- Student-specific optimization, eventually informed by longitudinal demand data

## What this is not

- Not an autonomous AI planner — the student always reviews and decides.
- Not an enrollment system — it exports class numbers; the student enrolls in MyASU.
- Not an advising replacement — it reduces advising friction; the institutional product makes
  advisors more effective, not redundant.

---

*Execution sequencing lives in [ROADMAP.md](ROADMAP.md).*
