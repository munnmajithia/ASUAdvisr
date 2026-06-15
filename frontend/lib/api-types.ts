// Shared types for the ASUAdvisr backend API.
//
// These mirror the Pydantic request/response models in
// backend/src/asuadvisr/api/main.py by hand — there is no codegen, so keep
// them in sync whenever the API contract changes.

export const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

/** Matches `Day = Literal["mon", ...]` in scheduler/constraints.py. */
export type Day = (typeof DAYS)[number];

/**
 * Matches `ConstraintsIn`. This is also the response shape of
 * `POST /parse-constraints`. Nullable fields are `null` (not omitted) so the
 * type round-trips cleanly through both request and response.
 *
 * The seat-filter / soft-preference fields below are `?`-optional: the backend
 * defaults them (`only_open=false`, `compact_schedule=false`,
 * `prefer_time_of_day=null`), so a request may omit them, while a
 * `/parse-constraints` response always includes them.
 */
export interface ApiConstraints {
  avoid_days: Day[];
  earliest_start: string | null; // "HH:MM", 24-hour
  latest_end: string | null; // "HH:MM", 24-hour
  min_credits: number | null;
  max_credits: number | null;
  preferred_modality: string | null; // "P" | "OL" | "HY" | …
  only_open?: boolean; // open-sections-only filter
  compact_schedule?: boolean; // soft pref: minimize gaps
  prefer_time_of_day?: string | null; // soft pref: "morning" | "afternoon" | "evening"
}

/** Response of `POST /parse-constraints` — same shape as a constraints input. */
export type ParsedConstraints = ApiConstraints;

/** Matches `RequirementIn`. */
export interface Requirement {
  course_keys: string[];
  pick: number;
}

/** Matches `ScheduleRequest`. */
export interface ScheduleRequest {
  requirements: Requirement[];
  constraints: ApiConstraints;
  max_results: number;
}

/** Matches `SectionDetail`. */
export interface SectionDetail {
  id: number;
  course_key: string;
  component: string;
  instruction_mode: string;
  days: string; // e.g. "MWF"
  time_range: string; // e.g. "9:00 AM - 9:50 AM" or "Async"
  enrl_stat: string; // 'O' open, 'C' closed, 'W' waitlist, 'X'
  is_open: boolean; // convenience flag: enrl_stat === 'O'
  instructors: string[]; // display names, e.g. ['Jane Doe']
}

/** Matches `ScheduleOut`. */
export interface ScheduleOut {
  sections: SectionDetail[];
  total_credits: number;
}

/** Matches `ScheduleResponse`. */
export interface ScheduleResponse {
  schedules: ScheduleOut[];
  count: number;
}

/** Response of `GET /courses`. */
export interface CoursesResponse {
  courses: string[];
}

/** Response of `GET /health`. */
export interface HealthResponse {
  status: string;
}
