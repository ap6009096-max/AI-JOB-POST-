# Run AI Job Post locally and in production

Local processes, Docker Compose, tests, and a pointer to production hosting. Do not put secrets in this file or in any `NEXT_PUBLIC_*` variable.

## Prerequisites

- Python 3.12+
- Node.js 20+ (for the Next.js app)
- Docker (optional, for Compose)
- A Supabase project (Postgres + Auth)

Copy [`.env.example`](../.env.example) to `.env` at the repo root and [`frontend/.env.example`](../frontend/.env.example) to `frontend/.env.local`. Never add `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `GITHUB_TOKEN`, or Reddit credentials to the frontend.

## Local — three terminals (Windows)

### 1. Frontend

```powershell
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000
- Health: http://localhost:3000/api/health
- Recruiter dashboard: http://localhost:3000/dashboard

### 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

For local Gemini without Vertex ADC, set `GEMINI_API_KEY` in root `.env`.

### 3. Worker

```powershell
cd worker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8081
```

- Health: http://localhost:8081/health
- `WORKER_URL=http://localhost:8081` in `.env`

Local resume files stay on disk (`RESUME_LOCAL_DIR` or the temp directory). Production uses GCS.

## Local — Docker Compose

From `infrastructure/`:

```powershell
cd infrastructure
docker compose --env-file ../.env up --build
```

[`docker-compose.yml`](../infrastructure/docker-compose.yml) maps:

- Frontend http://localhost:3000
- Backend http://localhost:8000
- Worker http://localhost:8081

Compose reads `../.env` for backend and worker. Frontend `NEXT_PUBLIC_*` values are **build args** (Next.js inlines them). Local compose bakes `NEXT_PUBLIC_API_URL=http://localhost:8000`. Do not add Postgres to Compose; use Supabase.

## Local checks

```powershell
cd backend
python -m pytest ../tests/backend

cd ../worker
python -m pytest ../tests/worker

cd ../frontend
npm test
```

After you publish a company job:

- Portal ranking: http://localhost:3000/dashboard/jobs/{jobId}/portal
- Internet talent search: http://localhost:3000/dashboard/jobs/{jobId}/internet

Those pages call `POST /v1/jobs/{id}/rank/portal` and `POST /v1/jobs/{id}/rank/internet`. The job must be `status=open`.

## Production

Production runs on **Google Cloud Run** (`aether-web`, `aether-api`, `aether-worker`), not Vercel or Render.

Full guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

| Piece | Host |
| --- | --- |
| Frontend | Cloud Run `aether-web` |
| API | Cloud Run `aether-api` |
| Worker | Cloud Run `aether-worker` (internal) |
| Postgres, Auth, RLS, pgvector | Supabase |
| Resume files | GCS |
| AI | Vertex Gemini (ADC) + Document AI |
| Queue | Cloud Tasks |

Push to `main` runs tests in [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Deploy via Cloud Build trigger or `gcloud builds submit`.

### Health after deploy

- API: `https://aether-api-....run.app/health`
- Web: `https://aether-web-....run.app/api/health`
- Worker: internal only (`/health` via Cloud Logging)

If the dashboard cannot call the API, check CORS (`CORS_ORIGINS` must be the `aether-web` origin) and rebuild the frontend after changing `NEXT_PUBLIC_API_URL`.

Sign in, then Create Job → Generate with AI to verify the full stack.

## Deprecated

`frontend/vercel.json` and `render.yaml` are legacy. See [DEPLOYMENT.md](DEPLOYMENT.md).
