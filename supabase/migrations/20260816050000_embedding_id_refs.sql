-- Vectors stay on public.embeddings. Profile and job rows store embedding_id only.

ALTER TABLE public.embeddings
  ADD COLUMN IF NOT EXISTS content_hash text NOT NULL DEFAULT '';

ALTER TABLE public.candidate_profiles
  ADD COLUMN IF NOT EXISTS embedding_id uuid REFERENCES public.embeddings (id) ON DELETE SET NULL;

ALTER TABLE public.jobs
  ADD COLUMN IF NOT EXISTS embedding_id uuid REFERENCES public.embeddings (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS candidate_profiles_embedding_id_idx ON public.candidate_profiles (embedding_id);
CREATE INDEX IF NOT EXISTS jobs_embedding_id_idx ON public.jobs (embedding_id);
