# Agent notes (Salesforce Core Automation)

IDE-only. There is no Next.js / Streamlit portal in this repo.

## Feature Memory / grounded test cases / scripts / runs

For Feature Memory, Jira→feature linking, analysis deltas, grounded test-case generation, approve/build Robot scripts, or running TC N / story tests in the IDE:

1. Follow [`.cursor/skills/feature-memory-qa/SKILL.md`](.cursor/skills/feature-memory-qa/SKILL.md).
2. Call APIs only via `py -3 scripts/feature_memory/cli.py` (see skill `reference.md`).
3. Never invent Salesforce facts; never enable RAG/catalog on the grounded path.
4. Never auto-accept Feature Memory deltas or auto-approve test cases.
5. Never fabricate `.robot` content — use `scripts build` / `scripts show`.
6. Map “TC N” with `cases list` + `--index N`. Runs need `--org`/`--persona` or `FEATURE_MEMORY_ORG_ID` / `FEATURE_MEMORY_PERSONA_ID`.

Human runbook: [`docs/IDE_FEATURE_MEMORY.md`](docs/IDE_FEATURE_MEMORY.md).

Cursor shorthand: `@feature-memory`.

## Backend surface (kept)

FastAPI routers used by the IDE path: `projects`, `features`, `user_stories`, `test_cases`, `orgs`, `personas`, `runs` (`/run`), `integrations` (Jira). Start with `scripts/feature_memory/start-backend.ps1` (`AUTH_DISABLED=true`).
