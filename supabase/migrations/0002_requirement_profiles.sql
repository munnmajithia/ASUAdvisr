-- M4 requirement profiles
-- Per-user degree-progress profiles extracted from DARS / major maps and confirmed
-- by the user. Written directly by the authenticated Supabase client; RLS scopes
-- every row to auth.uid(). service_role still bypasses RLS (as in 0001).
-- Field names mirror the RequirementProfile contract in
-- backend/src/asuadvisr/llm/requirement_profile.py.

-- ─── Profile root ──────────────────────────────────────────────────────────────
CREATE TABLE requirement_profiles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    catalog_year TEXT,
    major        TEXT,
    source       TEXT NOT NULL DEFAULT 'dars',  -- 'dars' | 'manual'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX requirement_profiles_user ON requirement_profiles (user_id);

CREATE OR REPLACE FUNCTION requirement_profiles_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER requirement_profiles_updated_at
    BEFORE UPDATE ON requirement_profiles
    FOR EACH ROW EXECUTE FUNCTION requirement_profiles_set_updated_at();

-- ─── Completed courses ───────────────────────────────────────────────────────────
CREATE TABLE profile_completed_courses (
    id          BIGSERIAL PRIMARY KEY,
    profile_id  UUID NOT NULL REFERENCES requirement_profiles (id) ON DELETE CASCADE,
    course_key  TEXT NOT NULL  -- 'SUBJECT CATALOG_NBR'
);

CREATE INDEX profile_completed_courses_profile ON profile_completed_courses (profile_id);

-- ─── Remaining required courses ────────────────────────────────────────────────
CREATE TABLE profile_required_courses (
    id          BIGSERIAL PRIMARY KEY,
    profile_id  UUID NOT NULL REFERENCES requirement_profiles (id) ON DELETE CASCADE,
    course_key  TEXT NOT NULL
);

CREATE INDEX profile_required_courses_profile ON profile_required_courses (profile_id);

-- ─── Choice groups (pick N of M) ────────────────────────────────────────────────
CREATE TABLE profile_choice_groups (
    id          BIGSERIAL PRIMARY KEY,
    profile_id  UUID NOT NULL REFERENCES requirement_profiles (id) ON DELETE CASCADE,
    name        TEXT NOT NULL DEFAULT '',
    pick        SMALLINT NOT NULL DEFAULT 1,
    filter      TEXT  -- textual fallback when no explicit keys are known
);

CREATE INDEX profile_choice_groups_profile ON profile_choice_groups (profile_id);

CREATE TABLE profile_choice_group_courses (
    id              BIGSERIAL PRIMARY KEY,
    choice_group_id BIGINT NOT NULL REFERENCES profile_choice_groups (id) ON DELETE CASCADE,
    course_key      TEXT NOT NULL
);

CREATE INDEX profile_choice_group_courses_group ON profile_choice_group_courses (choice_group_id);

-- ─── Row-level security ───────────────────────────────────────────────────────
-- Unlike 0001 (no policies; service_role-only), these tables are written by the
-- authenticated anon client, so every table gets owner-scoped policies. Each policy
-- targets the `authenticated` role and ties access to auth.uid() via the profile.
ALTER TABLE requirement_profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_completed_courses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_required_courses     ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_choice_groups        ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_choice_group_courses ENABLE ROW LEVEL SECURITY;

CREATE POLICY requirement_profiles_owner ON requirement_profiles
    FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY profile_completed_courses_owner ON profile_completed_courses
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM requirement_profiles p
                   WHERE p.id = profile_id AND p.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM requirement_profiles p
                        WHERE p.id = profile_id AND p.user_id = auth.uid()));

CREATE POLICY profile_required_courses_owner ON profile_required_courses
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM requirement_profiles p
                   WHERE p.id = profile_id AND p.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM requirement_profiles p
                        WHERE p.id = profile_id AND p.user_id = auth.uid()));

CREATE POLICY profile_choice_groups_owner ON profile_choice_groups
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM requirement_profiles p
                   WHERE p.id = profile_id AND p.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM requirement_profiles p
                        WHERE p.id = profile_id AND p.user_id = auth.uid()));

CREATE POLICY profile_choice_group_courses_owner ON profile_choice_group_courses
    FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM profile_choice_groups g
                   JOIN requirement_profiles p ON p.id = g.profile_id
                   WHERE g.id = choice_group_id AND p.user_id = auth.uid()))
    WITH CHECK (EXISTS (SELECT 1 FROM profile_choice_groups g
                        JOIN requirement_profiles p ON p.id = g.profile_id
                        WHERE g.id = choice_group_id AND p.user_id = auth.uid()));
