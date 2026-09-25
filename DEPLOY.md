# Deploying the API (IDE / backend only)

This repo ships a **FastAPI backend** for Feature Memory QA and Robot runs. There is no browser frontend to deploy.

| Service | Where | Notes |
|---------|-------|--------|
| **Backend** (FastAPI + Robot + RF-MCP) | **Fly.io** Machines + volume, or Docker locally | Spawns `robot` / Chromium; writes `Results/`, `Saved_Projects/`, data dirs |

Local IDE use does not require Fly — run `scripts/feature_memory/start-backend.ps1` or `docker compose up --build`.

---

## Architecture

```
Cursor / CLI
  |
  v
FastAPI :8000  -- subprocess: robot + chromium
               -- subprocess: RF-MCP :8765 (optional)
               -- volume / data dirs:
                    Results/
                    Saved_Projects/
                    ai_qa_portal/data/
                    ai_qa_portal/outputs/
```

---

## Prerequisites

- Docker (for compose / Fly image builds)
- Optional: `flyctl` for production
- Secrets in `.env` (never commit):
  - `FERNET_KEY` — generate once:
    ```bash
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```
  - LLM keys (`GEMINI_API_KEY`, `CURSOR_API_KEY`, …)
  - `AUTH_DISABLED=true` for IDE pilot (no Google OAuth)
  - Optional `DATABASE_URL` for Postgres + pgvector (empty → SQLite under `DATA_DIR`)

### Local Postgres

```bash
docker compose up -d postgres

DATABASE_URL='postgresql+psycopg://portal:portal@localhost:5432/portal' \
    python -m alembic -c ai_qa_portal/alembic.ini upgrade head
```

---

## Local prod-like (docker compose)

```bash
docker compose up --build
```

- API: `http://localhost:8000`
- Health: `GET /health`
- OpenAPI: `http://localhost:8000/docs`

Point the Feature Memory CLI at it (`FEATURE_MEMORY_API` / default `http://127.0.0.1:8000`).

---

## Fly.io (API)

1. Install `flyctl` and log in.
2. Create/app use existing app from [`fly.toml`](fly.toml) (`sf-core-automation-api` or your name).
3. Create a volume for `/data` if needed.
4. Set secrets (`FERNET_KEY`, LLM keys, `AUTH_DISABLED` or Google auth vars, `DATABASE_URL`, …).
5. Deploy:

```bash
fly deploy
```

CORS defaults to localhost only. For remote IDE clients, set `EXTRA_CORS_ORIGINS` / `CORS_ORIGINS` accordingly.

---

## IDE smoke after deploy

```powershell
$env:FEATURE_MEMORY_API = "https://<your-api-host>"
py -3 scripts/feature_memory/cli.py status
```

See [`docs/IDE_FEATURE_MEMORY.md`](docs/IDE_FEATURE_MEMORY.md).
