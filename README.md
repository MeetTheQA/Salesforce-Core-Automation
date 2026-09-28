# Salesforce Core Automation (IDE)

**AI-driven Salesforce QA from the IDE** — Feature Memory, grounded test-case generation, Robot script build, and sandbox runs. No browser portal.

Primary path: Cursor (or VS Code) + FastAPI on `localhost:8000` + [`scripts/feature_memory/cli.py`](scripts/feature_memory/cli.py).

Full runbook: [`docs/IDE_FEATURE_MEMORY.md`](docs/IDE_FEATURE_MEMORY.md). **Test commands:** [`docs/IDE_QA_TEST_RUNBOOK.md`](docs/IDE_QA_TEST_RUNBOOK.md). Agent rules: [`AGENTS.md`](AGENTS.md). Skill: `@feature-memory`.

---

## What you get

| Capability | Description |
|------------|-------------|
| **Feature Memory** | Editable per-feature knowledge with propose/accept deltas (no auto-accept). |
| **Grounded generation** | Test cases from Feature Memory only — RAG/catalog disabled on that path. |
| **Approve → build → run** | Human approve TCs, build `.robot` under `Saved_Projects/`, run via `/run`. |
| **Jira intake** | Import/link stories via integrations API (optional). |
| **LLM failover** | Gemini / OpenAI / Anthropic / Groq / Cursor SDK / Ollama, etc. |

---

## Prerequisites

- **Python 3.10+** (3.11+ recommended)
- **Node.js 20 LTS** (only if using Cursor SDK as LLM)
- A **Salesforce sandbox** (org + persona credentials in the backend)
- LLM API keys in `.env` (see [`.env.example`](.env.example))

---

## Setup

```bash
python -m venv .venv
```

**Windows**

```bat
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set at least one LLM key and keep `AUTH_DISABLED=true` for the IDE pilot.

### Start the API

```powershell
.\scripts\feature_memory\start-backend.ps1
```

Or:

```bash
AUTH_DISABLED=true uvicorn ai_qa_portal.backend.main:app --reload --port 8000
```

Smoke:

```powershell
py -3 scripts/feature_memory/cli.py status
```

---

## Typical QA loop (IDE)

1. `features list` / `features create` / `features seed`
2. Edit memory → `stories analyze` → **you** accept/reject deltas
3. `stories generate --feature …` (grounded)
4. `cases list` → **you** approve → `scripts build` → `runs case --index N`

Details and flags: [`.cursor/skills/feature-memory-qa/SKILL.md`](.cursor/skills/feature-memory-qa/SKILL.md).

---

## Docker (API only)

```bash
docker compose up --build
```

Postgres + FastAPI on `:8000`. See [`DEPLOY.md`](DEPLOY.md) for Fly.io.

---

## Project layout (essentials)

| Path | Role |
|------|------|
| `ai_qa_portal/backend/` | FastAPI (features, stories, cases, orgs, personas, `/run`, Jira) |
| `scripts/feature_memory/` | CLI + start-backend for IDE agents |
| `Saved_Projects/` | Generated `.robot` suites and project data |
| `Results/` | Robot run artifacts (also served at `/results`) |
| `docs/IDE_FEATURE_MEMORY.md` | Human IDE runbook |
| `docs/IDE_QA_TEST_RUNBOOK.md` | Common commands + best test process |

---

## Docs

- [`docs/IDE_FEATURE_MEMORY.md`](docs/IDE_FEATURE_MEMORY.md) — IDE pilot
- [`docs/IDE_QA_TEST_RUNBOOK.md`](docs/IDE_QA_TEST_RUNBOOK.md) — commands + E2E test loop
- [`docs/jira-integration.md`](docs/jira-integration.md) — Jira (optional)
- [`docs/cursor-sdk-integration.md`](docs/cursor-sdk-integration.md) — Cursor LLM
- [`DEPLOY.md`](DEPLOY.md) — backend deploy
