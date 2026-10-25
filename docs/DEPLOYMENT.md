# AI Job Post — production deployment

Production hosting is **Google Cloud Run** with Supabase for database, auth, and RLS. Do not put secrets in this file or in any `NEXT_PUBLIC_*` variable.

For the full environment variable matrix, see [env-where.md](env-where.md).

## Architecture

```text
GitHub
  ↓
Cloud Build (infrastructure/cloudbuild.yaml)
  ↓
Artifact Registry (aether-hire)
  ↓
Cloud Run
  ├── aether-web      (public HTTPS, Next.js standalone)
  ├── aether-api      (public HTTPS, FastAPI)
  └── aether-worker   (internal ingress, authenticated)
```

```mermaid
flowchart TD
  GitHub --> CloudBuild
  CloudBuild --> ArtifactRegistry
  ArtifactRegistry --> aetherWeb[aether-web]
  ArtifactRegistry --> aetherApi[aether-api]
  ArtifactRegistry --> aetherWorker[aether-worker]
  aetherWeb --> SupabaseAuth[Supabase Auth]
  aetherApi --> SupabaseDB[(Supabase Postgres)]
  aetherApi --> GCS[GCS resumes]
  aetherApi --> CloudTasks[Cloud Tasks]
  CloudTasks -->|OIDC| aetherWorker
  aetherWorker --> Vertex[Vertex Gemini]
  aetherWorker --> DocAI[Document AI]
  aetherApi --> Vertex
  aetherApi --> SecretManager[Secret Manager]
```

| Concern | Production choice |
| --- | --- |
| Web | Cloud Run `aether-web` |
| API | Cloud Run `aether-api` |
| Worker | Cloud Run `aether-worker` (ingress: internal) |
| LLM | Vertex AI Gemini via ADC — **do not set** `GEMINI_API_KEY` |
| OCR | Document AI when `DOCUMENT_AI_PROCESSOR_ID` is set; pypdf + Gemini multimodal fallback |
| Resume files | GCS (`GCS_BUCKET`) |
| Job queue | Cloud Tasks → `POST /tasks` with OIDC |
| Secrets | Secret Manager |
| Database / Auth / RLS / pgvector | Supabase |
| Logs / metrics | Cloud Logging + Cloud Monitoring |

Default region: `asia-south1`. Default GCP project in scripts: `imagi-ai-gpami`.

---

## Prerequisites

1. **Google Cloud project** with billing enabled
2. **`gcloud` CLI** installed and authenticated (`gcloud auth login`)
3. **Supabase project** (Postgres connection string, Auth, publishable + service role keys)
4. **GitHub repository** connected for CI (tests) and optionally Cloud Build triggers (deploy)
5. **Document AI processor** (optional but recommended for OCR) — create in GCP Console or use an existing processor ID

---

## 1. One-time GCP bootstrap

From the repo root (`ai-job-post/`):

```powershell
.\infrastructure\scripts\bootstrap_gcp.ps1 -ProjectId imagi-ai-gpami -Region asia-south1
```

This script (idempotent where `gcloud` allows):

- Enables APIs: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Cloud Tasks, Vertex AI, Document AI, Cloud Storage, Logging, Monitoring, IAM
- Creates Artifact Registry repo `aether-hire`
- Creates GCS bucket `aether-hire-resumes-PROJECT_ID`
- Creates Cloud Tasks queue `aether-hire-tasks`
- Creates service accounts: `aether-web`, `aether-api`, `aether-worker`
- Grants IAM roles (Vertex, Document AI, Storage, Cloud Tasks enqueuer, Secret Accessor, Logging, etc.)
- Creates Secret Manager secret **placeholders** (no values yet)

If bootstrap fails with `BILLING_NOT_OPEN`, enable billing on the GCP project and re-run.

---

## 2. Secret Manager

Create secret **versions** for each placeholder. Never commit these values to git.

| Secret name | Used by | Value |
| --- | --- | --- |
| `database-url` | API, worker | Supabase Postgres connection string (`postgresql://...`) |
| `supabase-service-role` | API, worker | Supabase service role key |
| `worker-shared-secret` | API, worker | Random string for `X-Worker-Secret` header |
| `github-token` | API (optional) | GitHub PAT for internet talent search |
| `reddit-client-id` | API (optional) | Reddit OAuth client ID |
| `reddit-client-secret` | API (optional) | Reddit OAuth client secret |

Example (PowerShell, from a file):

```powershell
# database-url
"postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres" | `
  gcloud secrets versions add database-url --data-file=-

# supabase-service-role
"eyJ..." | gcloud secrets versions add supabase-service-role --data-file=-

# worker-shared-secret
openssl rand -hex 32 | gcloud secrets versions add worker-shared-secret --data-file=-
```

On Windows without `openssl`, generate a random string another way and pipe it to `--data-file=-`.

---

## 3. Supabase setup

### Migrations

Apply SQL migrations in order from [`supabase/migrations/`](../supabase/migrations/):

1. `20260816013000_production_core_schema.sql`
2. `20260816020000_security_advisor_fixes.sql`
3. `20260816030000_auth_roles_rls.sql`
4. `20260816040000_candidate_profile_versions.sql`
5. `20260816050000_embedding_id_refs.sql`
6. `20260817000000_resume_storage_bucket.sql`

Use the Supabase CLI (`supabase db push`) or run each file in the Supabase SQL editor.

### Auth redirect URLs

After the first deploy, note the `aether-web` Cloud Run URL (e.g. `https://aether-web-xxxxx-as.a.run.app`).

In **Supabase Dashboard → Authentication → URL Configuration**:

- **Site URL**: `https://aether-web-xxxxx-as.a.run.app`
- **Redirect URLs**: add
  - `https://aether-web-xxxxx-as.a.run.app/auth/callback`
  - `http://localhost:3000/auth/callback` (for local dev)

If using Google OAuth, add the Cloud Run web origin to the Google Cloud OAuth client's authorized JavaScript origins.

### RLS

Row Level Security is enabled on all public tables via migrations. Do not disable RLS on exposed schemas.

---

## 4. Build and deploy

Cloud Build config: [`infrastructure/cloudbuild.yaml`](../infrastructure/cloudbuild.yaml)

### Substitution variables

Set these when submitting a build or in a Cloud Build trigger:

| Substitution | Description |
| --- | --- |
| `_NEXT_PUBLIC_API_URL` | Public URL of `aether-api` (e.g. `https://aether-api-xxxxx-as.a.run.app`) |
| `_FRONTEND_ORIGIN` | Public URL of `aether-web` (used for `CORS_ORIGINS` on API) |
| `_WORKER_URL` | URL of `aether-worker` (internal; used by Cloud Tasks OIDC audience) |
| `_GCS_BUCKET` | GCS bucket name (e.g. `aether-hire-resumes-imagi-ai-gpami`) |
| `_CLOUD_TASKS_QUEUE` | Queue name (`aether-hire-tasks`) |
| `_DOCUMENT_AI_PROCESSOR_ID` | Document AI processor ID (or empty to skip) |
| `_SUPABASE_URL` | `https://YOUR_PROJECT.supabase.co` |
| `_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key |
| `_NEXT_PUBLIC_SUPABASE_URL` | Same as `_SUPABASE_URL` (baked into frontend image) |
| `_NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Same as publishable key (baked into frontend image) |
| `_NEXT_PUBLIC_ENVIRONMENT` | Baked into frontend image (default `production`; rarely needs override) |

Built-in defaults in `cloudbuild.yaml`: `_REGION=asia-south1`, `_REPOSITORY=aether-hire`, `_NEXT_PUBLIC_ENVIRONMENT=production`, `_GEMINI_MODEL=gemini-2.0-flash-001`, `_GCS_BUCKET=aether-hire-resumes`, `_CLOUD_TASKS_QUEUE=aether-hire-tasks`.

### Manual deploy

From repo root:

```powershell
gcloud builds submit --config infrastructure/cloudbuild.yaml `
  --substitutions=_NEXT_PUBLIC_API_URL=https://aether-api-XXXX-as.a.run.app,_FRONTEND_ORIGIN=https://aether-web-XXXX-as.a.run.app,_WORKER_URL=https://aether-worker-XXXX-as.a.run.app,_GCS_BUCKET=aether-hire-resumes-imagi-ai-gpami,_CLOUD_TASKS_QUEUE=aether-hire-tasks,_SUPABASE_URL=https://YOUR_PROJECT.supabase.co,_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...,_NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co,_NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...,_DOCUMENT_AI_PROCESSOR_ID=YOUR_PROCESSOR_ID
```

**First deploy chicken-and-egg:** URLs are unknown until services exist. Options:

1. Deploy once with placeholder URLs, read actual Cloud Run URLs from the console, then redeploy with correct substitutions.
2. Create Cloud Run services manually first, then pass real URLs to Cloud Build.

### Cloud Build GitHub trigger (recommended)

1. Connect the GitHub repo in Cloud Build → Triggers
2. Trigger on push to `main`
3. Config file: `infrastructure/cloudbuild.yaml`
4. Set all `_...` substitutions in the trigger settings

### What Cloud Build does

1. Builds Docker images for `backend`, `worker`, `frontend`
2. Pushes to `asia-south1-docker.pkg.dev/PROJECT_ID/aether-hire/`
3. Deploys `aether-api`, `aether-worker`, `aether-web` to Cloud Run with env vars and Secret Manager mounts

---

## 5. Cloud Run services

Reference Knative templates: [`infrastructure/cloudrun/`](../infrastructure/cloudrun/)

| Service | Ingress | Auth | Health probe |
| --- | --- | --- | --- |
| `aether-web` | all (public) | unauthenticated | `GET /api/health` |
| `aether-api` | all (public) | unauthenticated | `GET /health`, `GET /ready` |
| `aether-worker` | internal | Cloud Tasks OIDC + `X-Worker-Secret` | `GET /health` |

Service accounts:

- `aether-api@PROJECT_ID.iam.gserviceaccount.com`
- `aether-worker@PROJECT_ID.iam.gserviceaccount.com`
- `aether-web@PROJECT_ID.iam.gserviceaccount.com`

---

## 6. Post-deploy configuration

1. **CORS** — `CORS_ORIGINS` on `aether-api` must equal the `aether-web` origin exactly (set via `_FRONTEND_ORIGIN` substitution).
2. **Supabase Auth** — redirect URLs must include the live `aether-web` URL (see section 3).
3. **Worker reachability** — Cloud Tasks invokes `aether-worker` with OIDC; the API service account (`aether-api`) must have `roles/run.invoker` on the worker (set by bootstrap script).
4. **Document AI** — if OCR quality is poor, confirm `DOCUMENT_AI_PROCESSOR_ID` is set and the Document AI API is enabled in the same region as the processor.

---

## 7. Verification

### Automated smoke test

```powershell
$env:API_URL = "https://aether-api-XXXX-as.a.run.app"
$env:WEB_URL = "https://aether-web-XXXX-as.a.run.app"
python scripts/production_smoke.py
```

### Health endpoints

```text
GET https://aether-api-XXXX-as.a.run.app/health
GET https://aether-api-XXXX-as.a.run.app/ready
GET https://aether-web-XXXX-as.a.run.app/api/health
```

Worker health is internal-only; check via Cloud Logging or `gcloud run services describe aether-worker`.

### Manual E2E checklist

- [ ] Candidate registration and login
- [ ] Resume upload, OCR, Gemini analysis, candidate JSON review
- [ ] Profile update (skills, experience, education)
- [ ] Company / recruiter registration
- [ ] Manual job creation and AI job generation
- [ ] Job publish and job JSON
- [ ] Portal ranking — Top 10, Top 20, Top 100
- [ ] Internet talent search — GitHub, portfolio, Reddit
- [ ] LinkedIn shows authorized-skip (no unauthorized scrape)
- [ ] Match details on portal and internet candidates

---

## 8. CI

[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) runs on push and pull requests to `main`:

- Backend: `pytest tests/backend`
- Worker: `pytest tests/worker`
- Frontend: `npm test`

Deploy to production is **not** done by GitHub Actions directly — use Cloud Build (manual submit or trigger on `main`).

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Bootstrap fails with `BILLING_NOT_OPEN` | GCP billing disabled | Enable billing on the project |
| API `/health` shows AI `not_configured` | Missing `GOOGLE_CLOUD_PROJECT` or ADC | Confirm env on Cloud Run; check service account has `roles/aiplatform.user` |
| Resume upload fails in production | GCS bucket missing or wrong `GCS_BUCKET` | Verify bucket exists; check API logs in Cloud Logging |
| Worker never processes resumes | Cloud Tasks misconfigured | Confirm `WORKER_URL`, queue name, and API SA can invoke worker |
| Dashboard API calls blocked | CORS mismatch | Set `CORS_ORIGINS` to exact `aether-web` origin; redeploy API |
| Auth redirect loop | Supabase redirect URL mismatch | Add `aether-web` callback URL in Supabase Auth settings |
| `429 Rate limit exceeded` | API rate limiter (production only) | Wait and retry; limits are per-instance sliding window |
| Gemini errors in production | Vertex quota or model name | Check `GEMINI_MODEL`; confirm Vertex AI API enabled |

View logs:

```powershell
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=aether-api" --limit=50 --format=json
```

---

## 10. Deprecated hosting

The following are **not** used for production:

- `frontend/vercel.json` — legacy Vercel config
- `render.yaml` — legacy Render blueprint
- `render.DEPRECATED.md` — deprecation notice

Production path: **GitHub → Cloud Build → Artifact Registry → Cloud Run**.
