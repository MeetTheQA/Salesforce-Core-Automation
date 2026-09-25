# Feature Memory API reference (IDE CLI)

Base URL: `http://127.0.0.1:8000` (no auth header when `AUTH_DISABLED=true`).

CLI: `py -3 scripts/feature_memory/cli.py --base URL <cmd>`

## Health

| Method | Path | CLI |
|---|---|---|
| GET | `/health` | `status` |

## Features — `/api/features`

| Method | Path | CLI |
|---|---|---|
| GET | `/api/features?project_id=` | `features list --project` |
| POST | `/api/features` body `{project_id,name,summary}` | `features create` |
| GET | `/api/features/{feature_id}` | `features get --feature` |
| POST | `/api/features/{feature_id}/seed` body `{template_id}` | `features seed --template` |
| GET | `/api/features/seed-templates?project_id=` | `seed-templates --project` |
| GET | `/api/features/review-queue?project_id=` | `review-queue --project` |
| GET | `/api/features/match-rules?project_id=` | `match-rules list --project` |
| POST | `/api/features/match-rules` body `{project_id,kind,key,feature_id}` | `match-rules set` |
| GET | `/api/features/{id}/memory` | `memory get` |
| PUT | `/api/features/{id}/memory` body `{reason,facts[]}` | `memory put` |
| GET | `/api/features/{id}/memory/deltas?status=` | `memory deltas` |
| POST | `/api/features/{id}/memory/deltas/{delta_id}/accept` | `memory accept` |
| POST | `/api/features/{id}/memory/deltas/{delta_id}/reject` | `memory reject` |
| GET | `/api/features/{id}/stories` | `stories list --feature` |
| POST | `/api/features/{id}/stories/{story_id}` | `stories link` |
| POST | `/api/features/{id}/stories/{story_id}/analyze` | `stories analyze` |

### Memory fact shape (PUT)

```json
{
  "reason": "manual_edit",
  "facts": [
    {
      "section": "rules",
      "text": "Rebate eligibility requires Active Account Status.",
      "source_kind": "user",
      "source_story_keys": [],
      "source_note": "offline BA note"
    }
  ]
}
```

`source_kind` values in product: `jira_story` | `analysis` | `user` | seed provenance tags.

## User stories — `/user-stories`

| Method | Path | CLI |
|---|---|---|
| GET | `/user-stories/{story_id}` | `stories get --story` |
| POST | `/user-stories/{story_id}/generate` | `stories generate --story --feature` |
| POST | `/user-stories/{story_id}/build-scripts` | `scripts build --story` |

### Grounded generate contract

When the story has `feature_id` set, the backend:

- requires a current analysis blob for that feature
- injects Feature Memory + related stories as grounded context
- disables RAG and catalog
- uses `grounded_test_case_drafter.md`

CLI `stories generate` additionally:

- asserts `story.feature_id == --feature`
- always records flags: `context_mode=feature_memory_only`, `use_rag=false`, `use_catalog=false`

Refuse generate if the story is unlinked.

## Test cases — `/test-cases`

| Method | Path | CLI |
|---|---|---|
| GET | `/test-cases?user_story_id=` | `cases list --story` (adds 1-based `index`) |
| GET | `/test-cases/{id}` | `cases get --story --case\|--index` |
| PATCH | `/test-cases/{id}` `{status:approved}` | `cases approve --story --case\|--index` |
| POST | `/test-cases/batch-approve` | `cases approve --story --all` |
| GET | `/test-cases/{id}/script` | `scripts show --story --case\|--index` |

“TC 3” in chat maps to `--index 3` against `cases list` order.

## Orgs / personas / runs

| Method | Path | CLI |
|---|---|---|
| GET | `/orgs` | `orgs list` |
| GET | `/personas` | `personas list` |
| POST | `/run/user-story/{id}` body `{org_id,persona_id?}` | `runs story --story --org [--persona]` |
| GET | `/run/test-case/{id}/stream?org_id=` | `runs case --story --index N --org` (SSE) |

Env defaults: `FEATURE_MEMORY_ORG_ID`, `FEATURE_MEMORY_PERSONA_ID`.

## Jira import (not wrapped by CLI yet)

`POST /projects/{slug}/integrations/jira/import` with `{issue_jira_ids, sprint_jira_ids}`.

After import, use `review-queue` and `match-rules` / `stories link`.

## Storage (check artifacts)

- Feature Memory + stories + draft TCs: `ai_qa_portal/data/` JSON files
- Robot scripts: `Saved_Projects/<slug>/Tests/Generated/story_<hex>/case_<hex>.robot` (path also on `script_path`)
- Per-QA fork: each machine keeps its own `data/` unless shared later
