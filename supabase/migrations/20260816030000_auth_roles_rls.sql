-- Product roles on public.users, private helpers, and tighter RLS.
-- Authorize from public.users.role / company_users, never user_metadata.

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS role text;

ALTER TABLE public.users
  DROP CONSTRAINT IF EXISTS users_role_check;

ALTER TABLE public.users
  ADD CONSTRAINT users_role_check
  CHECK (role IS NULL OR role IN ('candidate', 'recruiter', 'company_admin', 'platform_admin'));

-- Membership/role lookups are SECURITY DEFINER in private so RLS policies
-- can read users/company_users without infinite recursion.
CREATE OR REPLACE FUNCTION private.current_app_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT id FROM public.users WHERE auth_user_id = auth.uid() LIMIT 1
$$;

CREATE OR REPLACE FUNCTION private.current_role()
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT role FROM public.users WHERE auth_user_id = auth.uid() LIMIT 1
$$;

CREATE OR REPLACE FUNCTION private.is_platform_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT COALESCE(
    (SELECT role FROM public.users WHERE auth_user_id = auth.uid() LIMIT 1) = 'platform_admin',
    false
  )
$$;

CREATE OR REPLACE FUNCTION private.company_membership_role(p_company_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT cu.role
  FROM public.company_users cu
  JOIN public.users u ON u.id = cu.user_id
  WHERE cu.company_id = p_company_id
    AND u.auth_user_id = auth.uid()
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION private.is_company_member(p_company_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.company_users cu
    JOIN public.users u ON u.id = cu.user_id
    WHERE cu.company_id = p_company_id
      AND u.auth_user_id = auth.uid()
  )
$$;

CREATE OR REPLACE FUNCTION private.is_company_admin(p_company_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.company_users cu
    JOIN public.users u ON u.id = cu.user_id
    WHERE cu.company_id = p_company_id
      AND u.auth_user_id = auth.uid()
      AND cu.role IN ('owner', 'admin')
  )
$$;

CREATE OR REPLACE FUNCTION private.owns_candidate(p_candidate_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.candidates c
    JOIN public.users u ON u.id = c.user_id
    WHERE c.id = p_candidate_id
      AND u.auth_user_id = auth.uid()
  )
$$;

CREATE OR REPLACE FUNCTION private.job_company_id(p_job_id uuid)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT company_id FROM public.jobs WHERE id = p_job_id
$$;

CREATE OR REPLACE FUNCTION private.has_company_membership()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.company_users cu
    JOIN public.users u ON u.id = cu.user_id
    WHERE u.auth_user_id = auth.uid()
  )
$$;

CREATE OR REPLACE FUNCTION private.protect_user_role()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO pg_catalog, public
AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND current_user IN ('authenticated', 'anon') THEN
    NEW.role := OLD.role;
    IF NOT private.is_platform_admin() THEN
      NEW.status := OLD.status;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS protect_user_role ON public.users;
CREATE TRIGGER protect_user_role
  BEFORE UPDATE ON public.users
  FOR EACH ROW
  EXECUTE FUNCTION private.protect_user_role();

CREATE OR REPLACE FUNCTION private.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
BEGIN
  INSERT INTO public.users (auth_user_id, email, full_name)
  VALUES (
    NEW.id,
    COALESCE(NEW.email, NEW.id::text || '@users.local'),
    COALESCE(NEW.raw_user_meta_data->>'full_name', '')
  )
  ON CONFLICT (auth_user_id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION private.handle_new_user();

GRANT USAGE ON SCHEMA private TO authenticated;
GRANT EXECUTE ON FUNCTION private.current_app_user_id() TO authenticated;
GRANT EXECUTE ON FUNCTION private.current_role() TO authenticated;
GRANT EXECUTE ON FUNCTION private.is_platform_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION private.company_membership_role(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION private.is_company_member(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION private.is_company_admin(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION private.owns_candidate(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION private.job_company_id(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION private.has_company_membership() TO authenticated;
REVOKE ALL ON FUNCTION private.handle_new_user() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION private.protect_user_role() FROM PUBLIC, anon, authenticated;

DROP POLICY IF EXISTS users_select_self ON public.users;
DROP POLICY IF EXISTS users_insert_self ON public.users;
DROP POLICY IF EXISTS users_update_self ON public.users;
DROP POLICY IF EXISTS candidates_select_own_or_company ON public.candidates;
DROP POLICY IF EXISTS candidates_write_own ON public.candidates;
DROP POLICY IF EXISTS candidate_profiles_select ON public.candidate_profiles;
DROP POLICY IF EXISTS candidate_profiles_write_own ON public.candidate_profiles;
DROP POLICY IF EXISTS candidate_experience_select ON public.candidate_experience;
DROP POLICY IF EXISTS candidate_experience_write_own ON public.candidate_experience;
DROP POLICY IF EXISTS candidate_education_select ON public.candidate_education;
DROP POLICY IF EXISTS candidate_education_write_own ON public.candidate_education;
DROP POLICY IF EXISTS candidate_skills_select ON public.candidate_skills;
DROP POLICY IF EXISTS candidate_skills_write_own ON public.candidate_skills;
DROP POLICY IF EXISTS candidate_projects_select ON public.candidate_projects;
DROP POLICY IF EXISTS candidate_projects_write_own ON public.candidate_projects;
DROP POLICY IF EXISTS candidate_certifications_select ON public.candidate_certifications;
DROP POLICY IF EXISTS candidate_certifications_write_own ON public.candidate_certifications;
DROP POLICY IF EXISTS candidate_sources_select ON public.candidate_sources;
DROP POLICY IF EXISTS candidate_sources_write_own ON public.candidate_sources;
DROP POLICY IF EXISTS companies_insert_authenticated ON public.companies;
DROP POLICY IF EXISTS companies_member_all ON public.companies;
DROP POLICY IF EXISTS company_users_insert_self ON public.company_users;
DROP POLICY IF EXISTS company_users_member_select ON public.company_users;
DROP POLICY IF EXISTS jobs_member_all ON public.jobs;
DROP POLICY IF EXISTS job_skills_member_all ON public.job_skills;
DROP POLICY IF EXISTS matching_runs_member_all ON public.matching_runs;
DROP POLICY IF EXISTS sourcing_runs_member_all ON public.sourcing_runs;
DROP POLICY IF EXISTS external_candidates_member_all ON public.external_candidates;
DROP POLICY IF EXISTS source_evidence_member_all ON public.source_evidence;
DROP POLICY IF EXISTS candidate_match_scores_member_all ON public.candidate_match_scores;
DROP POLICY IF EXISTS match_results_member_all ON public.match_results;
DROP POLICY IF EXISTS embeddings_member_select ON public.embeddings;
DROP POLICY IF EXISTS audit_logs_select_own ON public.audit_logs;
DROP POLICY IF EXISTS audit_logs_insert_own ON public.audit_logs;

CREATE POLICY users_select_self ON public.users
  FOR SELECT TO authenticated
  USING (auth_user_id = auth.uid() OR private.is_platform_admin());

CREATE POLICY users_insert_self ON public.users
  FOR INSERT TO authenticated
  WITH CHECK (auth_user_id = auth.uid() AND role IS NULL);

CREATE POLICY users_update_self ON public.users
  FOR UPDATE TO authenticated
  USING (auth_user_id = auth.uid() OR private.is_platform_admin())
  WITH CHECK (auth_user_id = auth.uid() OR private.is_platform_admin());

CREATE POLICY candidates_select_own ON public.candidates
  FOR SELECT TO authenticated
  USING (user_id = private.current_app_user_id() OR private.is_platform_admin());

CREATE POLICY candidates_write_own ON public.candidates
  FOR ALL TO authenticated
  USING (user_id = private.current_app_user_id())
  WITH CHECK (user_id = private.current_app_user_id());

CREATE POLICY candidate_profiles_own ON public.candidate_profiles
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_experience_own ON public.candidate_experience
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_education_own ON public.candidate_education
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_skills_own ON public.candidate_skills
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_projects_own ON public.candidate_projects
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_certifications_own ON public.candidate_certifications
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY candidate_sources_own ON public.candidate_sources
  FOR ALL TO authenticated
  USING (private.owns_candidate(candidate_id) OR private.is_platform_admin())
  WITH CHECK (private.owns_candidate(candidate_id));

CREATE POLICY companies_select_member ON public.companies
  FOR SELECT TO authenticated
  USING (private.is_company_member(id) OR private.is_platform_admin());

CREATE POLICY companies_admin_update ON public.companies
  FOR UPDATE TO authenticated
  USING (private.is_company_admin(id))
  WITH CHECK (private.is_company_admin(id));

CREATE POLICY company_users_select_member ON public.company_users
  FOR SELECT TO authenticated
  USING (
    user_id = private.current_app_user_id()
    OR private.is_company_member(company_id)
    OR private.is_platform_admin()
  );

CREATE POLICY company_users_admin_insert ON public.company_users
  FOR INSERT TO authenticated
  WITH CHECK (private.is_company_admin(company_id));

CREATE POLICY company_users_admin_update ON public.company_users
  FOR UPDATE TO authenticated
  USING (private.is_company_admin(company_id))
  WITH CHECK (private.is_company_admin(company_id));

CREATE POLICY company_users_admin_delete ON public.company_users
  FOR DELETE TO authenticated
  USING (private.is_company_admin(company_id));

CREATE POLICY jobs_select_member ON public.jobs
  FOR SELECT TO authenticated
  USING (private.is_company_member(company_id) OR private.is_platform_admin());

CREATE POLICY jobs_admin_insert ON public.jobs
  FOR INSERT TO authenticated
  WITH CHECK (private.is_company_admin(company_id));

CREATE POLICY jobs_admin_update ON public.jobs
  FOR UPDATE TO authenticated
  USING (private.is_company_admin(company_id))
  WITH CHECK (private.is_company_admin(company_id));

CREATE POLICY jobs_admin_delete ON public.jobs
  FOR DELETE TO authenticated
  USING (private.is_company_admin(company_id));

CREATE POLICY job_skills_select_member ON public.job_skills
  FOR SELECT TO authenticated
  USING (
    private.is_company_member(private.job_company_id(job_id))
    OR private.is_platform_admin()
  );

CREATE POLICY job_skills_admin_write ON public.job_skills
  FOR ALL TO authenticated
  USING (private.is_company_admin(private.job_company_id(job_id)))
  WITH CHECK (private.is_company_admin(private.job_company_id(job_id)));

CREATE POLICY matching_runs_select_member ON public.matching_runs
  FOR SELECT TO authenticated
  USING (
    private.is_company_member(private.job_company_id(job_id))
    OR private.is_platform_admin()
  );

CREATE POLICY matching_runs_member_write ON public.matching_runs
  FOR ALL TO authenticated
  USING (private.is_company_member(private.job_company_id(job_id)))
  WITH CHECK (private.is_company_member(private.job_company_id(job_id)));

CREATE POLICY sourcing_runs_select_member ON public.sourcing_runs
  FOR SELECT TO authenticated
  USING (
    private.is_company_member(private.job_company_id(job_id))
    OR private.is_platform_admin()
  );

CREATE POLICY sourcing_runs_member_write ON public.sourcing_runs
  FOR ALL TO authenticated
  USING (private.is_company_member(private.job_company_id(job_id)))
  WITH CHECK (private.is_company_member(private.job_company_id(job_id)));

CREATE POLICY external_candidates_select_member ON public.external_candidates
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.sourcing_runs sr
      WHERE sr.id = sourcing_run_id
        AND (
          private.is_company_member(private.job_company_id(sr.job_id))
          OR private.is_platform_admin()
        )
    )
  );

CREATE POLICY external_candidates_member_write ON public.external_candidates
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.sourcing_runs sr
      WHERE sr.id = sourcing_run_id
        AND private.is_company_member(private.job_company_id(sr.job_id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.sourcing_runs sr
      WHERE sr.id = sourcing_run_id
        AND private.is_company_member(private.job_company_id(sr.job_id))
    )
  );

CREATE POLICY source_evidence_select_member ON public.source_evidence
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.external_candidates ec
      JOIN public.sourcing_runs sr ON sr.id = ec.sourcing_run_id
      WHERE ec.id = external_candidate_id
        AND (
          private.is_company_member(private.job_company_id(sr.job_id))
          OR private.is_platform_admin()
        )
    )
  );

CREATE POLICY source_evidence_member_write ON public.source_evidence
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.external_candidates ec
      JOIN public.sourcing_runs sr ON sr.id = ec.sourcing_run_id
      WHERE ec.id = external_candidate_id
        AND private.is_company_member(private.job_company_id(sr.job_id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.external_candidates ec
      JOIN public.sourcing_runs sr ON sr.id = ec.sourcing_run_id
      WHERE ec.id = external_candidate_id
        AND private.is_company_member(private.job_company_id(sr.job_id))
    )
  );

CREATE POLICY candidate_match_scores_select_member ON public.candidate_match_scores
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND (
          private.is_company_member(private.job_company_id(mr.job_id))
          OR private.is_platform_admin()
        )
    )
  );

CREATE POLICY candidate_match_scores_member_write ON public.candidate_match_scores
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND private.is_company_member(private.job_company_id(mr.job_id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND private.is_company_member(private.job_company_id(mr.job_id))
    )
  );

CREATE POLICY match_results_select_member ON public.match_results
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND (
          private.is_company_member(private.job_company_id(mr.job_id))
          OR private.is_platform_admin()
        )
    )
  );

CREATE POLICY match_results_member_write ON public.match_results
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND private.is_company_member(private.job_company_id(mr.job_id))
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      WHERE mr.id = run_id
        AND private.is_company_member(private.job_company_id(mr.job_id))
    )
  );

CREATE POLICY embeddings_select_member ON public.embeddings
  FOR SELECT TO authenticated
  USING (private.is_platform_admin() OR private.has_company_membership());

CREATE POLICY audit_logs_select_own ON public.audit_logs
  FOR SELECT TO authenticated
  USING (actor_user_id = private.current_app_user_id() OR private.is_platform_admin());

CREATE POLICY audit_logs_insert_own ON public.audit_logs
  FOR INSERT TO authenticated
  WITH CHECK (actor_user_id = private.current_app_user_id());
