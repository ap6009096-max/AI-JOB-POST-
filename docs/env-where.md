# Where each environment variable goes

Production host: **Google Cloud Run** (`aether-web` / `aether-api` / `aether-worker`).
Local: root `.env` + `frontend/.env.local`. See [.env.example](../.env.example).

| Variable | Local | aether-web | aether-api | aether-worker |
| --- | --- | --- | --- | --- |
| `NEXT_PUBLIC_ENVIRONMENT` | frontend `.env.local` | Cloud Build arg | — | — |
| `NEXT_PUBLIC_API_URL` | frontend `.env.local` | Cloud Build arg | — | — |
| `NEXT_PUBLIC_SUPABASE_URL` | frontend `.env.local` | Cloud Build arg | — | — |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | frontend `.env.local` | Cloud Build arg | — | — |
| `ENVIRONMENT` | root `.env` | — | Cloud Run env | Cloud Run env |
| `DATABASE_URL` | root `.env` | — | Secret Manager | Secret Manager |
| `SUPABASE_URL` | root `.env` | — | Cloud Run env | Cloud Run env |
| `SUPABASE_PUBLISHABLE_KEY` | root `.env` | — | Cloud Run env | Cloud Run env |
| `SUPABASE_SERVICE_ROLE_KEY` | root `.env` | **never** | Secret Manager | Secret Manager |
| `GOOGLE_CLOUD_PROJECT` | root `.env` | — | Cloud Run env | Cloud Run env |
| `GOOGLE_CLOUD_LOCATION` | root `.env` | — | Cloud Run env | Cloud Run env |
| `GEMINI_MODEL` | root `.env` | — | Cloud Run env | Cloud Run env |
| `GEMINI_API_KEY` | root `.env` (local only) | **never** | **do not set** (use Vertex ADC) | **do not set** |
| `GCS_BUCKET` | optional | — | Cloud Run env | Cloud Run env |
| `CLOUD_TASKS_QUEUE` | optional | — | Cloud Run env | Cloud Run env |
| `DOCUMENT_AI_PROCESSOR_ID` | optional | — | Cloud Run env | Cloud Run env |
| `WORKER_URL` | root `.env` | — | Cloud Run env | — |
| `BACKEND_URL` | root `.env` | — | — | Cloud Run env |
| `WORKER_SHARED_SECRET` | root `.env` | **never** | Secret Manager | Secret Manager |
| `CORS_ORIGINS` | root `.env` | — | Cloud Run env (web origin) | — |
| `GITHUB_TOKEN` | root `.env` | **never** | Secret Manager (optional) | — |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | root `.env` | **never** | Secret Manager (optional) | — |

## Notes

- Staging/production **require** `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET`, `CLOUD_TASKS_QUEUE` (API), and Vertex ADC — not `GEMINI_API_KEY`.
- Resume uploads go to **GCS** in non-local environments.
- LinkedIn sourcing stays on the authorized-skip policy (no unauthorized scrape).
