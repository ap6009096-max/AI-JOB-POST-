# Local development

Copy `.env.example` to `.env` at the repo root (and `frontend/.env.local` for Next.js public vars).

For Docker Compose, production hosting, secrets, and post-deploy health checks, use [run-local-and-cloud.md](run-local-and-cloud.md).

## Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000
- Health: http://localhost:3000/api/health

## Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs
- Company dashboard (frontend): http://localhost:3000/dashboard

Portal ranking and internet talent search call `POST /v1/jobs/{id}/rank/portal` and `.../rank/internet`.

## Worker

```bash
cd worker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8081
```

## Docker Compose

From `infrastructure/`:

```bash
docker compose up --build
```

## Tests

```bash
cd backend
python -m pytest ../tests/backend

cd ../worker
python -m pytest ../tests/worker
```
