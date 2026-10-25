-- AI Job Post production core schema.
-- RLS on every public table. updated_at trigger lives in private (not public SECURITY DEFINER).
-- Vectors live only on public.embeddings. Profile and job rows store embedding_id pointers, not the vector.

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE SCHEMA IF NOT EXISTS private;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

CREATE OR REPLACE FUNCTION private.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO pg_catalog, public
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TABLE public.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_user_id uuid UNIQUE REFERENCES auth.users (id) ON DELETE SET NULL,
  email text NOT NULL UNIQUE,
  full_name text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  role text CHECK (role IS NULL OR role IN ('candidate', 'recruiter', 'company_admin', 'platform_admin')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid UNIQUE REFERENCES public.users (id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'hidden')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL UNIQUE REFERENCES public.candidates (id) ON DELETE CASCADE,
  headline text NOT NULL DEFAULT '',
  summary text NOT NULL DEFAULT '',
  location text NOT NULL DEFAULT '',
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_experience (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  company_name text NOT NULL,
  title text NOT NULL,
  start_date date,
  end_date date,
  description text NOT NULL DEFAULT '',
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_education (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  school text NOT NULL,
  degree text NOT NULL DEFAULT '',
  field_of_study text NOT NULL DEFAULT '',
  start_date date,
  end_date date,
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_skills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  skill text NOT NULL,
  years numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (candidate_id, skill)
);

CREATE TABLE public.candidate_projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  url text,
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_certifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  name text NOT NULL,
  issuer text NOT NULL DEFAULT '',
  issued_on date,
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  source text NOT NULL,
  url text,
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_profile_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES public.candidates (id) ON DELETE CASCADE,
  version integer NOT NULL,
  snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  change_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  source text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (candidate_id, version)
);

CREATE TABLE public.companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  website text,
  extras jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.company_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner', 'admin', 'recruiter')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, user_id)
);

CREATE TABLE public.jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
  title text NOT NULL,
  description text NOT NULL DEFAULT '',
  location text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'closed')),
  requirements jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.job_skills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs (id) ON DELETE CASCADE,
  skill text NOT NULL,
  weight numeric NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (job_id, skill)
);

CREATE TABLE public.matching_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs (id) ON DELETE CASCADE,
  track text NOT NULL CHECK (track IN ('portal', 'internet')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  params jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.sourcing_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.jobs (id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  query jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.external_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sourcing_run_id uuid NOT NULL REFERENCES public.sourcing_runs (id) ON DELETE CASCADE,
  source text NOT NULL,
  url text,
  display_name text NOT NULL DEFAULT '',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.source_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_candidate_id uuid NOT NULL REFERENCES public.external_candidates (id) ON DELETE CASCADE,
  kind text NOT NULL,
  body jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.candidate_match_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.matching_runs (id) ON DELETE CASCADE,
  candidate_id uuid REFERENCES public.candidates (id) ON DELETE CASCADE,
  external_candidate_id uuid REFERENCES public.external_candidates (id) ON DELETE CASCADE,
  score numeric NOT NULL,
  parts jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (candidate_id IS NOT NULL AND external_candidate_id IS NULL)
    OR (candidate_id IS NULL AND external_candidate_id IS NOT NULL)
  )
);

CREATE TABLE public.match_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.matching_runs (id) ON DELETE CASCADE,
  rank integer NOT NULL CHECK (rank > 0),
  score numeric NOT NULL,
  candidate_id uuid REFERENCES public.candidates (id) ON DELETE CASCADE,
  external_candidate_id uuid REFERENCES public.external_candidates (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, rank),
  CHECK (
    (candidate_id IS NOT NULL AND external_candidate_id IS NULL)
    OR (candidate_id IS NULL AND external_candidate_id IS NOT NULL)
  )
);

CREATE TABLE public.embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type text NOT NULL CHECK (owner_type IN ('candidate_profile', 'job', 'external_candidate')),
  owner_id uuid NOT NULL,
  model text NOT NULL,
  embedding vector(768) NOT NULL,
  content_hash text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_type, owner_id, model)
);

ALTER TABLE public.candidate_profiles
  ADD COLUMN IF NOT EXISTS embedding_id uuid REFERENCES public.embeddings (id) ON DELETE SET NULL;

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS embedding_id uuid REFERENCES public.embeddings (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS candidate_profiles_embedding_id_idx ON public.candidate_profiles (embedding_id);
CREATE INDEX IF NOT EXISTS jobs_embedding_id_idx ON public.jobs (embedding_id);

CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id uuid REFERENCES public.users (id) ON DELETE SET NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX users_auth_user_id_idx ON public.users (auth_user_id);
CREATE INDEX candidates_user_id_idx ON public.candidates (user_id);
CREATE INDEX candidate_experience_candidate_id_idx ON public.candidate_experience (candidate_id);
CREATE INDEX candidate_education_candidate_id_idx ON public.candidate_education (candidate_id);
CREATE INDEX candidate_skills_candidate_id_idx ON public.candidate_skills (candidate_id);
CREATE INDEX candidate_projects_candidate_id_idx ON public.candidate_projects (candidate_id);
CREATE INDEX candidate_certifications_candidate_id_idx ON public.candidate_certifications (candidate_id);
CREATE INDEX candidate_sources_candidate_id_idx ON public.candidate_sources (candidate_id);
CREATE INDEX candidate_profile_versions_candidate_id_idx ON public.candidate_profile_versions (candidate_id, version DESC);
CREATE INDEX company_users_user_id_idx ON public.company_users (user_id);
CREATE INDEX company_users_company_id_idx ON public.company_users (company_id);
CREATE INDEX jobs_company_id_idx ON public.jobs (company_id);
CREATE INDEX job_skills_job_id_idx ON public.job_skills (job_id);
CREATE INDEX matching_runs_job_id_created_at_idx ON public.matching_runs (job_id, created_at DESC);
CREATE INDEX sourcing_runs_job_id_created_at_idx ON public.sourcing_runs (job_id, created_at DESC);
CREATE INDEX external_candidates_sourcing_run_id_idx ON public.external_candidates (sourcing_run_id);
CREATE INDEX source_evidence_external_candidate_id_idx ON public.source_evidence (external_candidate_id);
CREATE INDEX candidate_match_scores_run_id_idx ON public.candidate_match_scores (run_id);
CREATE INDEX candidate_match_scores_candidate_id_idx ON public.candidate_match_scores (candidate_id);
CREATE INDEX match_results_run_id_idx ON public.match_results (run_id);
CREATE INDEX embeddings_owner_idx ON public.embeddings (owner_type, owner_id);
CREATE INDEX audit_logs_actor_user_id_idx ON public.audit_logs (actor_user_id);
CREATE INDEX audit_logs_entity_idx ON public.audit_logs (entity_type, entity_id);
CREATE INDEX candidate_profiles_extras_gin ON public.candidate_profiles USING gin (extras);
CREATE INDEX jobs_requirements_gin ON public.jobs USING gin (requirements);
CREATE INDEX embeddings_hnsw ON public.embeddings USING hnsw (embedding vector_cosine_ops);

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'users', 'candidates', 'candidate_profiles', 'candidate_experience',
    'candidate_education', 'candidate_skills', 'candidate_projects',
    'candidate_certifications', 'candidate_sources', 'candidate_profile_versions', 'companies', 'company_users',
    'jobs', 'job_skills', 'matching_runs', 'sourcing_runs', 'external_candidates',
    'source_evidence', 'candidate_match_scores', 'match_results', 'embeddings',
    'audit_logs'
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION private.set_updated_at()',
      t
    );
  END LOOP;
END $$;

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_experience ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_education ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_certifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.matching_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sourcing_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.candidate_match_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.match_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

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

CREATE POLICY candidates_select_own_or_company ON public.candidates
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = candidates.user_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidates_write_own ON public.candidates
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = candidates.user_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = candidates.user_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_profiles_select ON public.candidate_profiles
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profiles.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_profiles_write_own ON public.candidate_profiles
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profiles.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profiles.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_experience_select ON public.candidate_experience
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_experience.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_experience_write_own ON public.candidate_experience
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_experience.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_experience.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_education_select ON public.candidate_education
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_education.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_education_write_own ON public.candidate_education
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_education.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_education.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_skills_select ON public.candidate_skills
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_skills.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_skills_write_own ON public.candidate_skills
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_skills.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_skills.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_projects_select ON public.candidate_projects
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_projects.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_projects_write_own ON public.candidate_projects
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_projects.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_projects.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_certifications_select ON public.candidate_certifications
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_certifications.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_certifications_write_own ON public.candidate_certifications
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_certifications.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_certifications.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_sources_select ON public.candidate_sources
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_sources.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_sources_write_own ON public.candidate_sources
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_sources.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_sources.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_profile_versions_select ON public.candidate_profile_versions
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profile_versions.candidate_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_profile_versions_write_own ON public.candidate_profile_versions
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profile_versions.candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.candidates c
      JOIN public.users u ON u.id = c.user_id
      WHERE c.id = candidate_profile_versions.candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY companies_insert_authenticated ON public.companies
  FOR INSERT TO authenticated
  WITH CHECK (true);

CREATE POLICY companies_member_all ON public.companies
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE cu.company_id = companies.id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE cu.company_id = companies.id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY company_users_insert_self ON public.company_users
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = company_users.user_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY company_users_member_select ON public.company_users
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = company_users.user_id AND u.auth_user_id = auth.uid()
    )
    OR EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE cu.company_id = company_users.company_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY jobs_member_all ON public.jobs
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE cu.company_id = jobs.company_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE cu.company_id = jobs.company_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY job_skills_member_all ON public.job_skills
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = job_skills.job_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = job_skills.job_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY matching_runs_member_all ON public.matching_runs
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = matching_runs.job_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = matching_runs.job_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY sourcing_runs_member_all ON public.sourcing_runs
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = sourcing_runs.job_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.jobs j
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE j.id = sourcing_runs.job_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY external_candidates_member_all ON public.external_candidates
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.sourcing_runs sr
      JOIN public.jobs j ON j.id = sr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE sr.id = external_candidates.sourcing_run_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.sourcing_runs sr
      JOIN public.jobs j ON j.id = sr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE sr.id = external_candidates.sourcing_run_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY source_evidence_member_all ON public.source_evidence
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.external_candidates ec
      JOIN public.sourcing_runs sr ON sr.id = ec.sourcing_run_id
      JOIN public.jobs j ON j.id = sr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE ec.id = source_evidence.external_candidate_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.external_candidates ec
      JOIN public.sourcing_runs sr ON sr.id = ec.sourcing_run_id
      JOIN public.jobs j ON j.id = sr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE ec.id = source_evidence.external_candidate_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY candidate_match_scores_member_all ON public.candidate_match_scores
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      JOIN public.jobs j ON j.id = mr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE mr.id = candidate_match_scores.run_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      JOIN public.jobs j ON j.id = mr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE mr.id = candidate_match_scores.run_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY match_results_member_all ON public.match_results
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      JOIN public.jobs j ON j.id = mr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE mr.id = match_results.run_id AND u.auth_user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.matching_runs mr
      JOIN public.jobs j ON j.id = mr.job_id
      JOIN public.company_users cu ON cu.company_id = j.company_id
      JOIN public.users u ON u.id = cu.user_id
      WHERE mr.id = match_results.run_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY embeddings_member_select ON public.embeddings
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.company_users cu
      JOIN public.users u ON u.id = cu.user_id
      WHERE u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY audit_logs_select_own ON public.audit_logs
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = audit_logs.actor_user_id AND u.auth_user_id = auth.uid()
    )
  );

CREATE POLICY audit_logs_insert_own ON public.audit_logs
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.users u
      WHERE u.id = audit_logs.actor_user_id AND u.auth_user_id = auth.uid()
    )
  );

-- After this file, apply supabase/migrations/20260816030000_auth_roles_rls.sql
-- (users.role, private auth helpers, and tighter role-aware RLS).
