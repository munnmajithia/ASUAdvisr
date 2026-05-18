-- M1.1 initial schema
-- Tables: terms, courses, section_groups, sections, meeting_times, instructors, section_instructors

-- ─── Terms ───────────────────────────────────────────────────────────────────
CREATE TABLE terms (
    id        SMALLINT PRIMARY KEY,  -- ASU STRM code (e.g. 2267)
    label     TEXT NOT NULL,         -- human-readable (e.g. 'Fall 2026')
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL
);

INSERT INTO terms (id, label, start_date, end_date)
VALUES (2267, 'Fall 2026', '2026-08-20', '2026-12-14');

-- ─── Courses ─────────────────────────────────────────────────────────────────
CREATE TABLE courses (
    id            TEXT PRIMARY KEY,  -- ASU CRSEID (stable across terms)
    subject       TEXT NOT NULL,     -- e.g. 'CSE'
    catalog_nbr   TEXT NOT NULL,     -- e.g. '100'
    title         TEXT NOT NULL,
    units_min     NUMERIC(4, 1) NOT NULL,
    units_max     NUMERIC(4, 1) NOT NULL,
    gs_designator TEXT,              -- RQMNTDESIGNTN, e.g. 'GS02'
    UNIQUE (subject, catalog_nbr)
);

-- ─── Section groups ───────────────────────────────────────────────────────────
-- Groups all sections that must be scheduled together (keyed by ASSOCIATEDCLASS).
-- A group with SSRCOUNT > 1 means the student needs one section from each
-- component type (e.g. one LEC + one LEL) within the group.
CREATE TABLE section_groups (
    id                 SERIAL PRIMARY KEY,
    term_id            SMALLINT NOT NULL REFERENCES terms (id),
    course_id          TEXT NOT NULL REFERENCES courses (id),
    assoc_class_label  TEXT NOT NULL,  -- CLAS.ASSOCIATEDCLASS value
    ssr_count          SMALLINT NOT NULL DEFAULT 1,  -- how many component types
    UNIQUE (term_id, course_id, assoc_class_label)
);

-- ─── Sections ─────────────────────────────────────────────────────────────────
CREATE TABLE sections (
    id                INTEGER PRIMARY KEY,  -- CLAS.CLASSNBR
    section_group_id  INTEGER NOT NULL REFERENCES section_groups (id),
    term_id           SMALLINT NOT NULL REFERENCES terms (id),
    course_id         TEXT NOT NULL REFERENCES courses (id),
    section_label     TEXT NOT NULL,  -- CLAS.CLASSSECTION (e.g. '1001')
    component         TEXT NOT NULL,  -- CLAS.SSRCOMPONENT: 'LEC', 'LEL', 'PRA', etc.
    instruction_mode  TEXT NOT NULL,  -- CLAS.INSTRUCTIONMODE: 'P', 'OL', 'HY', etc.
    campus            TEXT NOT NULL,  -- CLAS.CAMPUS
    location          TEXT,           -- CLAS.LOCATION (e.g. 'ASUONLINE')
    facility_id       TEXT,           -- CLAS.FACILITYID (room)
    enrl_cap          INTEGER NOT NULL,
    enrl_tot          INTEGER NOT NULL,
    enrl_stat         TEXT NOT NULL CHECK (enrl_stat IN ('O', 'C', 'W', 'X')),
    wait_cap          INTEGER NOT NULL DEFAULT 0,
    wait_tot          INTEGER NOT NULL DEFAULT 0,
    combined_id       TEXT,           -- CLAS.SCTNCOMBINEDID (cross-listing key; empty = not cross-listed)
    session_code      TEXT,           -- CLAS.SESSIONCODE (e.g. 'A', 'B', 'C')
    start_date        DATE,
    end_date          DATE,
    scraped_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX sections_term_course ON sections (term_id, course_id);
CREATE INDEX sections_combined_id ON sections (combined_id) WHERE combined_id IS NOT NULL AND combined_id <> '';

-- ─── Meeting times ────────────────────────────────────────────────────────────
-- One row per distinct meeting time per section.
-- Most sections have one row; hybrid sections may have two (one sync + one async,
-- but we only store rows where start_time IS NOT NULL).
CREATE TABLE meeting_times (
    id                   SERIAL PRIMARY KEY,
    section_id           INTEGER NOT NULL REFERENCES sections (id) ON DELETE CASCADE,
    mon                  BOOLEAN NOT NULL DEFAULT FALSE,
    tue                  BOOLEAN NOT NULL DEFAULT FALSE,
    wed                  BOOLEAN NOT NULL DEFAULT FALSE,
    thu                  BOOLEAN NOT NULL DEFAULT FALSE,
    fri                  BOOLEAN NOT NULL DEFAULT FALSE,
    sat                  BOOLEAN NOT NULL DEFAULT FALSE,
    sun                  BOOLEAN NOT NULL DEFAULT FALSE,
    start_time           TIME,
    end_time             TIME,
    meeting_start_date   DATE,
    meeting_end_date     DATE
);

CREATE INDEX meeting_times_section ON meeting_times (section_id);

-- ─── Instructors ─────────────────────────────────────────────────────────────
CREATE TABLE instructors (
    emplid      TEXT PRIMARY KEY,  -- ASU employee ID (from 'Name~emplid' encoding)
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL
);

-- ─── Section–instructor join ──────────────────────────────────────────────────
CREATE TABLE section_instructors (
    section_id  INTEGER NOT NULL REFERENCES sections (id) ON DELETE CASCADE,
    emplid      TEXT NOT NULL REFERENCES instructors (emplid),
    role        TEXT NOT NULL DEFAULT 'PI',  -- CLAS.INSTRROLE
    PRIMARY KEY (section_id, emplid)
);

-- ─── Row-level security ───────────────────────────────────────────────────────
-- Enabled from day 1; no public policies (service_role bypasses RLS for scraper).
-- Add SELECT policies in M3 when auth is wired.
ALTER TABLE terms             ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses           ENABLE ROW LEVEL SECURITY;
ALTER TABLE section_groups    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections          ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_times     ENABLE ROW LEVEL SECURITY;
ALTER TABLE instructors       ENABLE ROW LEVEL SECURITY;
ALTER TABLE section_instructors ENABLE ROW LEVEL SECURITY;
