---
name: feature-memory-qa
description: >-
  Runs the Feature Knowledge Brain / Feature Memory QA loop against local
  FastAPI: Jira feature link, editable Feature Memory, propose-then-accept
  analysis deltas, grounded test-case generation without RAG or catalog,
  approve cases, build per-TC Robot scripts, and run one case or a whole
  story. Use when the user mentions Feature Memory, grounded test cases,
  Salesforce Core QA brain, analyze deltas, feature match/review-queue,
  approve test cases, build Robot scripts, run TC N, execute story tests,
  or IDE-agent workflows that must not hallucinate Salesforce behavior.
---

# Feature Memory QA (IDE)

Backend-only playbook for Cursor / VS Code / Antigravity agents. Prefer the CLI
over inventing curl or API paths.

```text
py -3 scripts/feature_memory/cli.py <command> ...
```

Default base: `http://127.0.0.1:8000` (`FEATURE_MEMORY_BASE_URL` override).
Pilot assumes `AUTH_DISABLED=true` (see `scripts/feature_memory/start-backend.ps1`).

Runs need Salesforce org/persona: `--org` / `--persona` or env
`FEATURE_MEMORY_ORG_ID` / `FEATURE_MEMORY_PERSONA_ID`.

Read [`reference.md`](reference.md) for endpoints. Copy patterns from [`examples.md`](examples.md).

## Mandatory sequence (fail closed)

Do not skip steps. If a prerequisite fails, stop and tell the user.

1. **Backend up** — `status` (or ask user to run `start-backend.ps1`).
2. **Resolve `project_id`** — ask the user if missing; never invent UUIDs.
3. **Stories + match** — list/import as needed; `review-queue --project`; set `match-rules` or `stories link` for unmatched.
4. **Feature exists** — `features list|create`. Seed (`features seed`) **only** if memory is empty **and** the user confirms a template from `seed-templates`.
5. **Edit memory first** when the user has offline/user facts — `memory get` / `memory put`. User edits beat model guesses.
6. **Analyze** — `stories analyze --feature … --story …`. Present proposed deltas. **Never auto-accept.**
7. **Accept/reject** — only after explicit user decision: `memory accept` / `memory reject`.
8. **Grounded generate only** — `stories generate --story … --feature …`.
   - CLI refuses if `feature_id` is missing or mismatched.
   - Locked flags: `context_mode=feature_memory_only`, `use_rag=false`, `use_catalog=false`.
   - Never enable RAG or catalog on this path.
9. **Report gaps** — cite provenance / missing facts. Do **not** invent Salesforce objects, fields, or flows that are absent from Feature Memory + story text.
10. **List cases** — `cases list --story …`. Map “TC 3” to `--index 3` (1-based).
11. **Approve** — only after user confirms: `cases approve --story … --all` or `--index N`. Never invent approvals.
12. **Build scripts** — `scripts build --story …`. Never fabricate `.robot` content.
13. **Show script** — `scripts show --story … --index N` when the user wants to inspect.
14. **Run** — `runs case --story … --index N --org …` or `runs story --story … --org …`. Ask for org/persona if unset.

## Hard constraints

- Never invent Feature Memory facts or Salesforce behavior.
- Never invent API paths; use the CLI or [`reference.md`](reference.md).
- Never silently merge memory deltas.
- Never invent Robot Framework code; always `scripts build` / `scripts show`.
- Prefer `scripts/feature_memory/cli.py` over freeform HTTP.

## CLI map

| Intent | Command |
|---|---|
| Health | `status` |
| Features | `features list\|get\|create\|seed` |
| Seeds | `seed-templates --project` |
| Memory | `memory get\|put\|deltas\|accept\|reject` |
| Match | `review-queue`, `match-rules list\|set` |
| Stories | `stories link\|list\|get\|analyze\|generate` |
| Cases | `cases list\|get\|approve` |
| Scripts | `scripts build\|show` |
| Orgs / personas | `orgs list`, `personas list` |
| Runs | `runs story\|case` |
