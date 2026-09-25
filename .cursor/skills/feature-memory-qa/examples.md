# Feature Memory QA — example agent sessions

Assume repo root cwd and backend already running with `AUTH_DISABLED=true`.

Replace `PROJECT_ID`, `FEATURE_ID`, `STORY_ID`, `DELTA_ID` with real UUIDs from prior JSON output.

---

## 1) Import + match (Rebate Program)

User: “I imported Jira 1442 and 1444 for Rebate Program. Link them to a feature.”

Agent:

```bash
py -3 scripts/feature_memory/cli.py status
py -3 scripts/feature_memory/cli.py features list --project PROJECT_ID
py -3 scripts/feature_memory/cli.py review-queue --project PROJECT_ID
```

If no feature yet:

```bash
py -3 scripts/feature_memory/cli.py features create --project PROJECT_ID --name "Rebate Program" --summary "Core rebate eligibility and payout"
```

Map labels / epic, or link explicitly:

```bash
py -3 scripts/feature_memory/cli.py match-rules set --project PROJECT_ID --kind label --key rebate --feature FEATURE_ID
py -3 scripts/feature_memory/cli.py stories link --feature FEATURE_ID --story STORY_1442_UUID
py -3 scripts/feature_memory/cli.py stories link --feature FEATURE_ID --story STORY_1444_UUID
py -3 scripts/feature_memory/cli.py stories list --feature FEATURE_ID
```

Do not invent match keys; use values from Jira / review-queue output.

---

## 2) Edit memory then analyze

User: “Add my offline note that rebates require Active Account, then analyze 1442.”

Agent:

```bash
py -3 scripts/feature_memory/cli.py memory get --feature FEATURE_ID
```

Write a temp JSON file (or `--facts-json`) with `source_kind: user`, then:

```bash
py -3 scripts/feature_memory/cli.py memory put --feature FEATURE_ID --file path/to/facts.json
py -3 scripts/feature_memory/cli.py stories analyze --feature FEATURE_ID --story STORY_1442_UUID
py -3 scripts/feature_memory/cli.py memory deltas --feature FEATURE_ID --status pending
```

Present `delta_id` + proposed facts to the user. **Stop.** Wait for accept/reject.

```bash
# only after user says accept
py -3 scripts/feature_memory/cli.py memory accept --feature FEATURE_ID --delta DELTA_ID
```

Never auto-accept.

---

## 3) Grounded generate for story X

User: “Create grounded test cases for 1442.”

Prerequisites already done: linked feature, analyze run, deltas handled as user directed.

```bash
py -3 scripts/feature_memory/cli.py stories get --story STORY_1442_UUID
py -3 scripts/feature_memory/cli.py stories generate --story STORY_1442_UUID --feature FEATURE_ID
```

Expected envelope includes `grounded_flags` with `feature_memory_only` / `use_rag: false` / `use_catalog: false`.

If CLI exits with REFUSE (no `feature_id`), link first — do not fall back to RAG/catalog generate.

Report draft case count, then invite the user to approve / build / run in a later turn.

---

## 4) Approve + build for story

User: “Approve all drafts for 1442 and build scripts.”

```bash
py -3 scripts/feature_memory/cli.py cases list --story STORY_1442_UUID
# only after user confirms
py -3 scripts/feature_memory/cli.py cases approve --story STORY_1442_UUID --all
py -3 scripts/feature_memory/cli.py scripts build --story STORY_1442_UUID
```

Show `built` / `skipped` from the response. If build refuses (no approved cases), approve first.

---

## 5) Run TC 3 only

User: “Show TC 3 script, then run just TC 3.”

```bash
py -3 scripts/feature_memory/cli.py cases list --story STORY_1442_UUID
py -3 scripts/feature_memory/cli.py scripts show --story STORY_1442_UUID --index 3
py -3 scripts/feature_memory/cli.py orgs list
py -3 scripts/feature_memory/cli.py personas list
py -3 scripts/feature_memory/cli.py runs case --story STORY_1442_UUID --index 3 --org ORG_ID --persona PERSONA_ID
```

`--index 3` means the third row from `cases list` (same order). Do not invent Robot code.

---

## 6) Run all for story

User: “Run all approved cases for 1442.”

```bash
py -3 scripts/feature_memory/cli.py runs story --story STORY_1442_UUID --org ORG_ID --persona PERSONA_ID
```

Or set `FEATURE_MEMORY_ORG_ID` / `FEATURE_MEMORY_PERSONA_ID` and omit flags.
