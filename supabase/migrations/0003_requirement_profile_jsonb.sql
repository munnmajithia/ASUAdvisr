-- M4 requirement profiles — richer schema (supersedes 0002's child tables).
--
-- The canonical extractor (backend/src/asuadvisr/llm/requirement_extractor.py)
-- produces a nested RequirementProfile:
--   completed_courses[{course,title,grade,term,credits,in_progress}]
--   remaining_requirements[{label,options[],pick,credits_needed,note}]
-- These are variable-shape and nested, so they live as JSONB on the profile row
-- rather than spread across the rigid child tables 0002 created. The frontend
-- (RLS-scoped Supabase client) reads/writes the whole profile in one row.
--
-- RLS on requirement_profiles (from 0002, USING/WITH CHECK auth.uid() = user_id)
-- still applies; service_role bypasses it.

ALTER TABLE requirement_profiles
    ADD COLUMN completed_courses      JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN remaining_requirements JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Drop the normalized child tables (and their RLS policies, via DROP TABLE).
DROP TABLE IF EXISTS profile_choice_group_courses;
DROP TABLE IF EXISTS profile_choice_groups;
DROP TABLE IF EXISTS profile_required_courses;
DROP TABLE IF EXISTS profile_completed_courses;
