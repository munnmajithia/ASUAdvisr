// Requirement-profile data layer.
//
// The TypeScript mirror of the Python `RequirementProfile` contract
// (backend/src/asuadvisr/llm/requirement_extractor.py) — the response shape of
// `POST /extract-requirements`. Field names and nullability match the Pydantic
// models exactly; keep them in sync when that contract changes.
//
// Persistence is frontend-only and deliberate: the backend is stateless, so the
// confirmed profile is written straight to Supabase via the authenticated
// browser client. Row-level security scopes every row to `auth.uid()`, so no
// `Authorization` header and no backend round-trip is involved. The whole
// profile lives in one `requirement_profiles` row, with the two arrays stored
// as JSONB (see supabase/migrations/0003_requirement_profile_jsonb.sql).

import type { Requirement } from "@/lib/api-types";
import { getBrowserSupabase } from "@/lib/supabase";

/** Mirrors Python `CompletedCourse` — a course taken or currently in progress. */
export interface CompletedCourse {
  course: string; // "SUBJECT NUMBER", e.g. "CSE 110"
  title: string | null;
  grade: string | null; // grade as printed; "NR" if in progress
  term: string | null; // term code if shown, e.g. "FA23"
  credits: number | null;
  in_progress: boolean;
}

/** Mirrors Python `RemainingRequirement` — take `pick` course(s) from `options`. */
export interface RemainingRequirement {
  label: string; // e.g. "CSE 355" or "CSE 412 OR CSE 434"
  options: string[]; // concrete course keys; EMPTY for wildcards/open electives
  pick: number; // how many of `options` to take
  credits_needed: number | null;
  note: string | null; // wildcard pattern / NOT-FROM exclusions, etc.
}

/** Mirrors Python `RequirementProfile` — what a student still needs to graduate. */
export interface RequirementProfile {
  catalog_year: string | null;
  major: string | null;
  completed_courses: CompletedCourse[];
  remaining_requirements: RemainingRequirement[];
}

/** The `requirement_profiles` table name (RLS-scoped to the owner). */
const TABLE = "requirement_profiles";

/** Persisted JSONB columns we read back; the arrays come through as `unknown`-ish
 *  JSON, so we cast them through the declared interfaces (never `any`). */
interface ProfileRow {
  catalog_year: string | null;
  major: string | null;
  completed_courses: CompletedCourse[] | null;
  remaining_requirements: RemainingRequirement[] | null;
}

/**
 * Persist the confirmed profile for the signed-in user.
 *
 * Single-profile-per-user with a clean replace: there is no unique constraint on
 * `user_id`, so we delete the user's existing row(s) then insert one fresh row
 * (rather than relying on upsert). `user_id` is taken from the session, not the
 * caller. Throws if not signed in or if Supabase reports an error.
 */
export async function saveProfile(profile: RequirementProfile): Promise<void> {
  const supabase = getBrowserSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");
  const userId = session.user.id;

  const { error: deleteError } = await supabase.from(TABLE).delete().eq("user_id", userId);
  if (deleteError) {
    throw new Error(`Failed to clear existing profile: ${deleteError.message}`);
  }

  const { error: insertError } = await supabase.from(TABLE).insert({
    user_id: userId,
    catalog_year: profile.catalog_year,
    major: profile.major,
    completed_courses: profile.completed_courses,
    remaining_requirements: profile.remaining_requirements,
  });
  if (insertError) {
    throw new Error(`Failed to save profile: ${insertError.message}`);
  }
}

/**
 * Load the signed-in user's profile, or `null` when none exists.
 *
 * RLS already scopes the query to the owner, so we just take the most recent
 * row. Returns `null` when there is no session or no stored profile. The JSONB
 * arrays are coalesced to `[]` when null.
 */
export async function loadProfile(): Promise<RequirementProfile | null> {
  const supabase = getBrowserSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) return null;

  const { data, error } = await supabase
    .from(TABLE)
    .select("catalog_year, major, completed_courses, remaining_requirements")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) {
    throw new Error(`Failed to load profile: ${error.message}`);
  }
  if (!data) return null;

  const row = data as ProfileRow;
  return {
    catalog_year: row.catalog_year,
    major: row.major,
    completed_courses: row.completed_courses ?? [],
    remaining_requirements: row.remaining_requirements ?? [],
  };
}

/**
 * Map a profile to scheduler input — the TS mirror of Python `to_requirements()`.
 *
 * Each remaining requirement with concrete `options` becomes a
 * `{ course_keys, pick }`. Requirements with no options (wildcards, open
 * electives, hour-based needs) are excluded — they can't be scheduled until the
 * student resolves them into concrete courses (see `unresolvedRequirements`),
 * and an empty `course_keys` would make the request unsatisfiable.
 */
export function profileToRequirements(profile: RequirementProfile): Requirement[] {
  return profile.remaining_requirements
    .filter((req) => req.options.length > 0)
    .map((req) => ({ course_keys: req.options, pick: req.pick }));
}

/**
 * Remaining requirements with no concrete `options` — the TS mirror of Python
 * `unresolved_requirements()`. These wildcard/open-elective/hour-based needs
 * can't be scheduled as-is; the review UI surfaces them so the student picks
 * concrete courses.
 */
export function unresolvedRequirements(profile: RequirementProfile): RemainingRequirement[] {
  return profile.remaining_requirements.filter((req) => req.options.length === 0);
}
