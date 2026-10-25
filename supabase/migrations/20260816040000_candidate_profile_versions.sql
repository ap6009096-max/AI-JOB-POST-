-- Versioned master candidate JSON. Standing profile rows stay candidate-owned.

CREATE TABLE IF NOT EXISTS public.candidate_profile_versions (
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

CREATE INDEX IF NOT EXISTS candidate_profile_versions_candidate_id_idx
  ON public.candidate_profile_versions (candidate_id, version DESC);

DROP TRIGGER IF EXISTS set_updated_at ON public.candidate_profile_versions;
CREATE TRIGGER set_updated_at
  BEFORE UPDATE ON public.candidate_profile_versions
  FOR EACH ROW EXECUTE FUNCTION private.set_updated_at();

ALTER TABLE public.candidate_profile_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS candidate_profile_versions_select ON public.candidate_profile_versions;
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

DROP POLICY IF EXISTS candidate_profile_versions_write_own ON public.candidate_profile_versions;
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
