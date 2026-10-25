-- Fix security advisors after the production core schema:
-- 1) move pgvector out of public (0014_extension_in_public)
-- 2) revoke client execute on leftover public SECURITY DEFINER helper (0028/0029)
--    Do not DROP: event trigger ensure_rls depends on public.rls_auto_enable().

CREATE SCHEMA IF NOT EXISTS extensions;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'vector' AND n.nspname = 'public'
  ) THEN
    ALTER EXTENSION vector SET SCHEMA extensions;
  END IF;
END $$;

REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;
