# IDE Feature Memory (backend-only pilot)

Run the Feature Knowledge Brain from Cursor / VS Code / Antigravity **without** the Next.js UI. Each QA uses a local FastAPI + their own `data/` fork.

## One-time setup

1. Clone the repo and install Python deps the way you normally run the portal backend.
2. Ensure local auth bypass for the pilot:
   - In backend `.env`: `AUTH_DISABLED=true`
   - Or rely on `scripts/feature_memory/start-backend.ps1` which sets `AUTH_DISABLED=true` for that process.
3. Start **backend only** (no frontend required):

```powershell
.\scripts\feature_memory\start-backend.ps1
```

4. Smoke:

```powershell
py -3 scripts/feature_memory/cli.py status
py -3 scripts/feature_memory/cli.py features list --project <PROJECT_UUID>
```

5. For runs, set org/persona once (optional):

```powershell
$env:FEATURE_MEMORY_ORG_ID = "<org-uuid>"
$env:FEATURE_MEMORY_PERSONA_ID = "<persona-uuid>"
# discover: py -3 scripts/feature_memory/cli.py orgs list
#           py -3 scripts/feature_memory/cli.py personas list
```

## Per-QA data

- Stories, Feature Memory, and draft test cases live under `ai_qa_portal/data/` (JSON file backend).
- Robot scripts land under `Saved_Projects/<project>/Tests/Generated/story_*/case_*.robot` (`script_path` on each case).
- Each machine is an independent fork. Optional later: share selected feature JSON via git — not required for this pilot.
- Do not commit secrets (`.env`, persona passwords).

## How to invoke

### Cursor

- Natural language that mentions Feature Memory / grounded test cases / build scripts / run TC (skill: `.cursor/skills/feature-memory-qa/`).
- Or explicit: `@feature-memory` then describe the step.

### VS Code / Antigravity / other agents

Follow root [`AGENTS.md`](../AGENTS.md): use the skill playbook and `scripts/feature_memory/cli.py`.

## Agent loop (summary)

1. `status`
2. Resolve `project_id`
3. `review-queue` / `match-rules` / `stories link`
4. `features create` + optional `features seed` (empty memory + user confirms)
5. `memory get` / `memory put` for offline notes
6. `stories analyze` → show deltas → **user** accept/reject
7. `stories generate --story --feature` (grounded flags locked)
8. `cases list` → **user** confirms → `cases approve` (`--all` or `--index N`)
9. `scripts build` → optional `scripts show --index N`
10. `runs case --index N --org …` or `runs story --org …`

Full detail: [`.cursor/skills/feature-memory-qa/SKILL.md`](../.cursor/skills/feature-memory-qa/SKILL.md).

## Manual smoke checklist

- [ ] Backend starts with `start-backend.ps1`
- [ ] `cli.py status` returns health JSON
- [ ] `features list --project …` returns `[]` or features (not 401)
- [ ] After linking a story, `stories generate` refuses when `--feature` mismatches
- [ ] `cases list` shows numbered indexes; `cases approve --all` then `scripts build` succeeds
- [ ] `scripts show --index 1` returns path + content
- [ ] `runs case` / `runs story` require org (or env) and do not invent UUIDs
