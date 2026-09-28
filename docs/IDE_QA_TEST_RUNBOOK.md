# IDE QA — common commands and best test process

Prefix every CLI call with:

```powershell
py -3 scripts/feature_memory/cli.py
```

Default API: `http://127.0.0.1:8000` (override with `$env:FEATURE_MEMORY_BASE_URL`).

Related: [`IDE_FEATURE_MEMORY.md`](IDE_FEATURE_MEMORY.md) (setup + data layout), [`.cursor/skills/feature-memory-qa/SKILL.md`](../.cursor/skills/feature-memory-qa/SKILL.md) (agent playbook).

---

## 0. One-time setup

```powershell
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Set at least one LLM key (GEMINI_API_KEY / CURSOR_API_KEY / …)
# Keep AUTH_DISABLED=true
```

Salesforce runs also need an org + persona already registered in the backend (credentials via projects/personas APIs or existing `Saved_Projects` data).

---

## 1. Fast automated smoke (no Salesforce)

```powershell
py -3 -m pytest ai_qa_portal/tests/test_feature_memory_cli_contract.py ai_qa_portal/tests/test_feature_matcher.py -q
```

Expect: CLI contract + matcher tests green. This does **not** prove LLM generate or Robot runs.

---

## 2. Start API + health

```powershell
.\scripts\feature_memory\start-backend.ps1
# other terminal:
py -3 scripts/feature_memory/cli.py status
```

Expect: `{"status":"ok"}`. OpenAPI: http://127.0.0.1:8000/docs

Optional Docker: `docker compose up --build` then same `status` against `:8000`.

---

## 3. Best end-to-end process (Feature Memory loop)

Do these in order. **Stop** if a step fails. Never auto-accept deltas or auto-approve cases.

```text
status
  -> Resolve project_id
  -> review-queue / stories link
  -> features create / seed
  -> memory get / put
  -> stories analyze
  -> User accept / reject deltas
  -> stories generate
  -> cases list
  -> User approve
  -> scripts build / show
  -> runs case or story
```

### A. Discover IDs

```powershell
# You need a real project UUID (ask team / list via API docs / existing data). Never invent UUIDs.
py -3 scripts/feature_memory/cli.py orgs list
py -3 scripts/feature_memory/cli.py personas list
$env:FEATURE_MEMORY_ORG_ID = "<org-uuid>"
$env:FEATURE_MEMORY_PERSONA_ID = "<persona-uuid>"
```

### B. Features + memory

```powershell
py -3 scripts/feature_memory/cli.py features list --project <PROJECT_UUID>
py -3 scripts/feature_memory/cli.py features create --project <PROJECT_UUID> --name "My Feature"
py -3 scripts/feature_memory/cli.py seed-templates --project <PROJECT_UUID>
# Only if memory empty AND you confirm template:
py -3 scripts/feature_memory/cli.py features seed --feature <FEATURE_UUID> --template <TEMPLATE_ID>
py -3 scripts/feature_memory/cli.py memory get --feature <FEATURE_UUID>
# Edit facts offline, then:
py -3 scripts/feature_memory/cli.py memory put --feature <FEATURE_UUID> --file memory.json
```

### C. Story link → analyze → generate

```powershell
py -3 scripts/feature_memory/cli.py review-queue --project <PROJECT_UUID>
py -3 scripts/feature_memory/cli.py stories link --feature <FEATURE_UUID> --story <STORY_UUID>
py -3 scripts/feature_memory/cli.py stories analyze --feature <FEATURE_UUID> --story <STORY_UUID>
py -3 scripts/feature_memory/cli.py memory deltas --feature <FEATURE_UUID>
# After YOU decide:
py -3 scripts/feature_memory/cli.py memory accept --feature <FEATURE_UUID> --delta <DELTA_ID>
# or: memory reject ...
py -3 scripts/feature_memory/cli.py stories generate --story <STORY_UUID> --feature <FEATURE_UUID>
```

Grounded flags are locked by the CLI (`feature_memory_only`, no RAG/catalog).

### D. Approve → build → inspect

```powershell
py -3 scripts/feature_memory/cli.py cases list --story <STORY_UUID>
# "TC 3" means --index 3 (1-based)
py -3 scripts/feature_memory/cli.py cases approve --story <STORY_UUID> --all
# or: --index 3
py -3 scripts/feature_memory/cli.py scripts build --story <STORY_UUID>
py -3 scripts/feature_memory/cli.py scripts show --story <STORY_UUID> --index 1
```

Scripts land under `Saved_Projects/<project>/Tests/Generated/story_*/case_*.robot`.

### E. Run against sandbox

```powershell
py -3 scripts/feature_memory/cli.py runs case --story <STORY_UUID> --index 1 --org <ORG_UUID>
# or whole story:
py -3 scripts/feature_memory/cli.py runs story --story <STORY_UUID> --org <ORG_UUID>
```

Artifacts: `Results/` (also http://127.0.0.1:8000/results/…).

---

## 4. Command cheat sheet

| Intent | Command |
|--------|---------|
| Health | `status` |
| Features | `features list\|get\|create\|seed` |
| Seed catalog | `seed-templates --project` |
| Memory | `memory get\|put\|deltas\|accept\|reject` |
| Match | `review-queue`, `match-rules list\|set` |
| Stories | `stories link\|list\|get\|analyze\|generate` |
| Cases | `cases list\|get\|approve` |
| Scripts | `scripts build\|show` |
| Targets | `orgs list`, `personas list` |
| Execute | `runs story\|case` |

In Cursor: `@feature-memory` + natural language; agents must use this CLI only ([`AGENTS.md`](../AGENTS.md), skill above).

---

## 5. What “good” looks like (manual checklist)

- [ ] `status` OK with backend up
- [ ] `features list` not 401
- [ ] Analyze proposes deltas; accept/reject only after human decision
- [ ] Generate refuses wrong/missing `--feature`
- [ ] `cases list` shows numbered indexes; approve then `scripts build` succeeds
- [ ] `scripts show --index 1` returns path + content
- [ ] `runs case` needs org (or env); Robot run produces Results artifacts

---

## Notes

- This is the **product test path** for QAs (IDE + sandbox).
- Unit pytest covers CLI/matcher only; LLM generate and Salesforce UI runs are manual/agent-driven.
