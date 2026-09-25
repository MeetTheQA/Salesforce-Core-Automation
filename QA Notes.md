# QA Notes

Short guide for QA engineers using the **QA** branch of this repository. For full setup and architecture detail, see **`README.md`**.

---

## Getting this code

```bash
git clone https://github.com/meettheqa-ast/Salesforce-Core-Automation.git
cd Salesforce-Core-Automation
git checkout QA
git pull origin QA
```

Use the **QA** branch for shared test automation work aligned with your team’s validation cycle. **`main`** holds the primary integration line; **`QA`** is the branch to pull for QA-focused drops.

---

## What this project is

**Salesforce Core Automation (IDE)** — a **FastAPI** backend (`ai_qa_portal/backend/`) plus **Robot Framework** assets for **Salesforce**, driven from the IDE via the Feature Memory CLI (`scripts/feature_memory/cli.py`). There is no browser portal. QAs describe work in Cursor; agents call the CLI for Feature Memory, grounded test cases, script build, and runs. LLM providers: Gemini / OpenAI / Anthropic / Groq / Cursor SDK / Ollama (failover). Runs need a Salesforce **sandbox** org + persona (credentials stored by the backend — not committed to git).

See [`docs/IDE_FEATURE_MEMORY.md`](docs/IDE_FEATURE_MEMORY.md) and [`AGENTS.md`](AGENTS.md).

---

## Main capabilities (what exists)

| Area | What it does |
|------|----------------|
| **Natural language → Robot** | LLM (Cursor SDK by default; Gemini, OpenAI, Anthropic, Groq, Ollama, etc. as failover) turns descriptions into executable Robot scripts using project keywords and locators. |
| **Keyword catalog** | Scans `Resources/PO` and related paths so generated tests align with real keywords and Page Objects. |
| **Self-healing UI keywords** | Shared Robot keywords retry saves, read Salesforce validation panels, and fill missing modal fields (picklists, text, etc.) to reduce flaky failures. |
| **Data-driven CSV** | CSV upload; when tests use **`@{LEADS_FROM_CSV}`**, **`CsvDataLibrary`** loads **`uploaded_test_data.csv`** and drives **FOR** loops over rows. |
| **Project workspace** | **`Saved_Projects/<name>/`** can hold tests, data, local config, and per-project **`Results/`** (not required for ad-hoc runs). |
| **Parallel runs (Pabot)** | Optional **Pabot** for running multiple test cases in parallel (project suite flows). |
| **In-app results** | Robot HTML/XML under `Results/`; also served at `GET /results` from the API. |
| **Human-in-the-loop** | Feature Memory deltas and test cases require explicit user accept/approve via CLI — no auto-accept. |
| **Modular Salesforce tests** | Repo layout supports apps/areas such as **LucyChatBot**, **OmsChatBot**, **Platform**, and **B2B** under **`Tests/`** and **`Resources/`** (Page Objects, env-specific data). |

---

## What QA should verify (suggested checklist)

Use this as a smoke / regression outline when validating a new **QA** build or release.

1. **Environment & API launch**
   - Python **3.10+**, **`pip install -r requirements.txt`**, start API via **`scripts/feature_memory/start-backend.ps1`** (or uvicorn). Confirm `cli.py status` → `ok`.
   - Salesforce sandbox login works when org/persona credentials are set (see **`docs/IDE_FEATURE_MEMORY.md`** — **`EnvData.robot`** is generated at run time and is **gitignored**).

2. **Feature Memory generation**
   - Grounded generate produces draft test cases; **you** accept deltas and approve cases (no auto-accept).
   - `scripts build` / `scripts show` produce real `.robot` under `Saved_Projects/`.

3. **Execution**
   - `runs case --index N` (or story run) opens the browser, reaches Salesforce, and completes a minimal flow against your sandbox.
   - **Results** land under **`Results/`** (or project Results) with **`log.html`**, **`output.xml`**, **`report.html`**.

4. **Self-healing / resilience**
   - If Salesforce shows validation errors after Save, healing keywords attempt to fix missing required fields without manual script edits (within supported cases).

5. **CSV-driven flows**
   - With a sample CSV, tests that use **`@{LEADS_FROM_CSV}`** iterate rows and behave consistently with **`CsvDataLibrary`** (headers normalized, row dict access).

6. **Parallel execution (if used)**
   - **Pabot** project suite runs complete without clashes; machine and Salesforce load remain acceptable (see **`README.md`** for process limits).

7. **Multi-module layout (optional, if your team uses these suites)**
   - Under **`Tests/`** and **`Resources/`**, area-specific folders (**LucyChatBot**, **OmsChatBot**, **Platform**, **B2B**) load the right **`*Common.robot`**, **`*Data.robot`**, **`*Env.robot`**, and **PO** files for that product line.

---

## Files QA often opens first

| File / folder | Why |
|---------------|-----|
| **`README.md`** | Install, features, architecture, prompt tips. |
| **`Documentation/Project Details.md`** | High-level folder map for tests and resources. |
| **`Tests/`** | Top-level Robot suites per application area. |
| **`Resources/Common/GlobalKeywords.robot`** | Shared Salesforce UI keywords (including self-heal behavior). |

---

## Security & data

- Do **not** commit **API keys**, **passwords**, or **customer CSVs** with real PII. Follow your org’s policy for sandboxes and LLM keys (typically **`.env`** / Streamlit secrets — see **`README.md`**).

---

*This document is maintained for the **QA** branch audience. For the latest platform behavior, always cross-check **`README.md`** on the same commit.*
