// Requirement-profile data layer.
//
// The frontend TypeScript mirror of the Python `RequirementProfile` contract
// (backend/src/asuadvisr/llm/requirement_profile.py). Per the locked persistence
// decision the backend is stateless, so the confirmed profile is read/written
// directly through the authenticated Supabase client — every row is RLS-scoped
// to auth.uid(). Table and column names match
// supabase/migrations/0002_requirement_profiles.sql.
//
// `profileToRequirements` re-implements the Python `to_requirements()` mapping so
// the same profile → scheduler-input shape is produced on both sides.

import type { Requirement } from "@/lib/api-types";
import { getBrowserSupabase } from "@/lib/supabase";

/** A "pick N of M" requirement set (e.g. a gen-studies bucket or elective pool).
 *  Mirrors `ChoiceGroup` in the Python contract. */
export interface ChoiceGroup {
  name: string;
  pick: number;
  course_keys: string[];
  filter: string | null; // textual fallback when no explicit keys are known
}

/** A student's degree-progress profile extracted from a DARS / major map.
 *  Mirrors `RequirementProfile` in the Python contract. */
export interface RequirementProfile {
  catalog_year: string | null;
  major: string | null;
  completed_courses: string[];
  required_courses_remaining: string[];
  choice_groups: ChoiceGroup[];
}

/** Map a profile to scheduler input — the TS twin of Python `to_requirements()`.
 *
 *  Each remaining required course → one `Requirement` (pick 1). Each choice group
 *  with explicit course keys → one `Requirement(pick=N)`. Completed courses are
 *  excluded; choice groups with only a textual `filter` and no keys are skipped
 *  (nothing concrete to schedule yet). */
export function profileToRequirements(profile: RequirementProfile): Requirement[] {
  const requirements: Requirement[] = profile.required_courses_remaining.map((course) => ({
    course_keys: [course],
    pick: 1,
  }));
  for (const group of profile.choice_groups) {
    if (group.course_keys.length > 0) {
      requirements.push({ course_keys: group.course_keys, pick: group.pick });
    }
  }
  return requirements;
}

/** Read the signed-in user's confirmed profile from Supabase, or `null` when no
 *  profile exists. Returns `null` (rather than throwing) when no user is signed
 *  in, so callers can treat "not authenticated" and "no profile yet" alike. */
export async function loadProfile(): Promise<RequirementProfile | null> {
  const supabase = getBrowserSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) return null;

  // RLS already scopes the row to the owner; take the most recent profile.
  const { data: profileRow, error: profileError } = await supabase
    .from("requirement_profiles")
    .select("id, catalog_year, major")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (profileError) throw new Error(`Failed to load profile: ${profileError.message}`);
  if (!profileRow) return null;

  const profileId = profileRow.id as string;

  const completed_courses = await loadCourseKeys("profile_completed_courses", profileId);
  const required_courses_remaining = await loadCourseKeys("profile_required_courses", profileId);

  const { data: groupRows, error: groupsError } = await supabase
    .from("profile_choice_groups")
    .select("id, name, pick, filter")
    .eq("profile_id", profileId);
  if (groupsError) throw new Error(`Failed to load choice groups: ${groupsError.message}`);

  const choice_groups: ChoiceGroup[] = [];
  for (const group of groupRows ?? []) {
    const { data: courseRows, error: coursesError } = await supabase
      .from("profile_choice_group_courses")
      .select("course_key")
      .eq("choice_group_id", group.id);
    if (coursesError)
      throw new Error(`Failed to load choice-group courses: ${coursesError.message}`);
    choice_groups.push({
      name: (group.name as string | null) ?? "",
      pick: group.pick as number,
      filter: (group.filter as string | null) ?? null,
      course_keys: (courseRows ?? []).map((row) => row.course_key as string),
    });
  }

  return {
    catalog_year: (profileRow.catalog_year as string | null) ?? null,
    major: (profileRow.major as string | null) ?? null,
    completed_courses,
    required_courses_remaining,
    choice_groups,
  };
}

/** Persist the user's confirmed profile, replacing any existing one. Children
 *  cascade-delete with the old root row, so this is a clean single-profile
 *  replace. Throws `Error("Not signed in")` when there is no session. */
export async function saveProfile(profile: RequirementProfile): Promise<void> {
  const supabase = getBrowserSupabase();

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");
  const userId = session.user.id;

  // Single profile per user: drop the old root (children cascade) before insert.
  const { error: deleteError } = await supabase
    .from("requirement_profiles")
    .delete()
    .eq("user_id", userId);
  if (deleteError) throw new Error(`Failed to clear existing profile: ${deleteError.message}`);

  // WITH CHECK requires user_id = auth.uid(), so set it explicitly.
  const { data: inserted, error: insertError } = await supabase
    .from("requirement_profiles")
    .insert({
      user_id: userId,
      catalog_year: profile.catalog_year,
      major: profile.major,
    })
    .select("id")
    .single();
  if (insertError) throw new Error(`Failed to create profile: ${insertError.message}`);
  const profileId = inserted.id as string;

  await saveCourseKeys("profile_completed_courses", profileId, profile.completed_courses);
  await saveCourseKeys("profile_required_courses", profileId, profile.required_courses_remaining);

  for (const group of profile.choice_groups) {
    const { data: groupRow, error: groupError } = await supabase
      .from("profile_choice_groups")
      .insert({
        profile_id: profileId,
        name: group.name,
        pick: group.pick,
        filter: group.filter,
      })
      .select("id")
      .single();
    if (groupError) throw new Error(`Failed to save choice group: ${groupError.message}`);

    if (group.course_keys.length > 0) {
      const { error: groupCoursesError } = await supabase
        .from("profile_choice_group_courses")
        .insert(
          group.course_keys.map((course_key) => ({
            choice_group_id: groupRow.id as number,
            course_key,
          })),
        );
      if (groupCoursesError)
        throw new Error(`Failed to save choice-group courses: ${groupCoursesError.message}`);
    }
  }
}

/** Read every `course_key` for a profile from one of the simple course tables. */
async function loadCourseKeys(
  table: "profile_completed_courses" | "profile_required_courses",
  profileId: string,
): Promise<string[]> {
  const supabase = getBrowserSupabase();
  const { data, error } = await supabase
    .from(table)
    .select("course_key")
    .eq("profile_id", profileId);
  if (error) throw new Error(`Failed to load ${table}: ${error.message}`);
  return (data ?? []).map((row) => row.course_key as string);
}

/** Bulk-insert `course_key` rows for a profile into one of the simple course
 *  tables. No-ops when the list is empty so empty arrays skip the round-trip. */
async function saveCourseKeys(
  table: "profile_completed_courses" | "profile_required_courses",
  profileId: string,
  courseKeys: string[],
): Promise<void> {
  if (courseKeys.length === 0) return;
  const supabase = getBrowserSupabase();
  const { error } = await supabase
    .from(table)
    .insert(courseKeys.map((course_key) => ({ profile_id: profileId, course_key })));
  if (error) throw new Error(`Failed to save ${table}: ${error.message}`);
}
