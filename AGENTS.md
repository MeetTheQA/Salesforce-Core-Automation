# Agent notes (Salesforce Core Automation)

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

## Frontend (Next.js)

Portal UI agents should also respect [`frontend/AGENTS.md`](frontend/AGENTS.md) when editing the Next.js app. Feature Memory pilot does **not** require the frontend.
