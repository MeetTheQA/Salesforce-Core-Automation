#!/usr/bin/env python3
"""Feature Memory IDE CLI — thin HTTP wrapper for local FastAPI.

Prefer this over ad-hoc curl. Grounded generate always forces anti-hallucination
mode (context_mode=feature_memory_only, use_rag=false, use_catalog=false).
The live generate endpoint auto-grounds when the story has feature_id; the CLI
refuses to call it unless --feature matches that link.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE = os.environ.get("FEATURE_MEMORY_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_ORG = os.environ.get("FEATURE_MEMORY_ORG_ID", "")
DEFAULT_PERSONA = os.environ.get("FEATURE_MEMORY_PERSONA_ID", "")

# Locked grounded-mode contract (phase-1 skill). Backend applies these when
# story.feature_id is set; CLI always emits and validates the same triple.
GROUNDED_GENERATE_FLAGS: dict[str, Any] = {
    "context_mode": "feature_memory_only",
    "use_rag": False,
    "use_catalog": False,
}


def grounded_generate_flags() -> dict[str, Any]:
    """Return the mandatory anti-hallucination flags (copy)."""
    return dict(GROUNDED_GENERATE_FLAGS)


def assert_grounded_flags(flags: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fail closed if any grounded flag is missing or wrong."""
    payload = grounded_generate_flags() if flags is None else dict(flags)
    expected = GROUNDED_GENERATE_FLAGS
    for key, value in expected.items():
        if key not in payload:
            raise ValueError(f"missing grounded flag: {key}")
        if payload[key] != value:
            raise ValueError(f"grounded flag {key}={payload[key]!r} must be {value!r}")
    return payload


def resolve_case_id(
    cases: list[dict[str, Any]],
    *,
    case_id: str | None = None,
    index: int | None = None,
) -> str:
    """Resolve --case UUID or 1-based --index against a cases list."""
    if case_id and index is not None:
        raise ValueError("pass --case or --index, not both")
    if case_id:
        wanted = str(case_id).strip().lower()
        for row in cases:
            if str(row.get("id", "")).lower() == wanted:
                return str(row["id"])
        raise ValueError(f"case id not in list: {case_id}")
    if index is None:
        raise ValueError("require --case <uuid> or --index N (1-based; TC 3 => --index 3)")
    if index < 1:
        raise ValueError(f"index must be >= 1, got {index}")
    if index > len(cases):
        raise ValueError(f"index {index} out of range (list has {len(cases)} cases)")
    return str(cases[index - 1]["id"])


def number_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach 1-based index for agent/QA 'TC N' mapping."""
    out: list[dict[str, Any]] = []
    for i, row in enumerate(cases, start=1):
        out.append(
            {
                "index": i,
                "id": row.get("id"),
                "title": row.get("title"),
                "status": row.get("status"),
                "stale": row.get("stale"),
                "script_path": row.get("script_path"),
                "script_built_at": row.get("script_built_at"),
            }
        )
    return out


def fetch_story_cases(base: str, story_id: str) -> list[dict[str, Any]]:
    data = _request(
        "GET",
        "/test-cases",
        base=base,
        query={"user_story_id": story_id},
    )
    if not isinstance(data, list):
        raise ValueError("unexpected test-cases response")
    return data


def resolve_org_id(args: argparse.Namespace) -> str:
    org = (getattr(args, "org", None) or DEFAULT_ORG or "").strip()
    if not org:
        raise SystemExit(
            "REFUSE: --org or FEATURE_MEMORY_ORG_ID required. Run: "
            "py -3 scripts/feature_memory/cli.py orgs list"
        )
    return org


def resolve_persona_id(args: argparse.Namespace) -> str | None:
    persona = (getattr(args, "persona", None) or DEFAULT_PERSONA or "").strip()
    return persona or None


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str, url: str) -> None:
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} {url}: {body[:500]}")


def _request(
    method: str,
    path: str,
    *,
    base: str,
    query: dict[str, Any] | None = None,
    body: Any | None = None,
) -> Any:
    url = base.rstrip("/") + path
    if query:
        qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        url = f"{url}?{qs}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, err_body, url) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach backend at {base}: {exc.reason}") from exc


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_status(args: argparse.Namespace) -> int:
    data = _request("GET", "/health", base=args.base)
    _print(data if data is not None else {"ok": True})
    return 0


def cmd_features_list(args: argparse.Namespace) -> int:
    data = _request(
        "GET",
        "/api/features",
        base=args.base,
        query={"project_id": args.project, "include_archived": str(args.include_archived).lower()},
    )
    _print(data)
    return 0


def cmd_features_get(args: argparse.Namespace) -> int:
    data = _request("GET", f"/api/features/{args.feature}", base=args.base)
    _print(data)
    return 0


def cmd_features_create(args: argparse.Namespace) -> int:
    body = {"project_id": args.project, "name": args.name, "summary": args.summary or ""}
    data = _request("POST", "/api/features", base=args.base, body=body)
    _print(data)
    return 0


def cmd_features_seed(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        f"/api/features/{args.feature}/seed",
        base=args.base,
        body={"template_id": args.template},
    )
    _print(data)
    return 0


def cmd_seed_templates(args: argparse.Namespace) -> int:
    data = _request(
        "GET",
        "/api/features/seed-templates",
        base=args.base,
        query={"project_id": args.project},
    )
    _print(data)
    return 0


def cmd_memory_get(args: argparse.Namespace) -> int:
    data = _request("GET", f"/api/features/{args.feature}/memory", base=args.base)
    _print(data)
    return 0


def cmd_memory_put(args: argparse.Namespace) -> int:
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            payload = json.load(fh)
    elif args.facts_json:
        payload = json.loads(args.facts_json)
    else:
        raise SystemExit("memory put requires --file or --facts-json")
    if isinstance(payload, list):
        body = {"reason": args.reason, "facts": payload}
    elif isinstance(payload, dict) and "facts" in payload:
        body = {"reason": payload.get("reason", args.reason), "facts": payload["facts"]}
    else:
        raise SystemExit("JSON must be a facts list or {reason, facts}")
    data = _request("PUT", f"/api/features/{args.feature}/memory", base=args.base, body=body)
    _print(data)
    return 0


def cmd_memory_deltas(args: argparse.Namespace) -> int:
    data = _request(
        "GET",
        f"/api/features/{args.feature}/memory/deltas",
        base=args.base,
        query={"status": args.status},
    )
    _print(data)
    return 0


def cmd_memory_accept(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        f"/api/features/{args.feature}/memory/deltas/{args.delta}/accept",
        base=args.base,
        body={"reason": args.reason},
    )
    _print(data)
    return 0


def cmd_memory_reject(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        f"/api/features/{args.feature}/memory/deltas/{args.delta}/reject",
        base=args.base,
        body={"reason": args.reason},
    )
    _print(data)
    return 0


def cmd_review_queue(args: argparse.Namespace) -> int:
    data = _request(
        "GET",
        "/api/features/review-queue",
        base=args.base,
        query={"project_id": args.project},
    )
    _print(data)
    return 0


def cmd_match_rules_list(args: argparse.Namespace) -> int:
    data = _request(
        "GET",
        "/api/features/match-rules",
        base=args.base,
        query={"project_id": args.project},
    )
    _print(data)
    return 0


def cmd_match_rules_set(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        "/api/features/match-rules",
        base=args.base,
        body={
            "project_id": args.project,
            "kind": args.kind,
            "key": args.key,
            "feature_id": args.feature,
        },
    )
    _print(data)
    return 0


def cmd_stories_link(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        f"/api/features/{args.feature}/stories/{args.story}",
        base=args.base,
    )
    _print(data)
    return 0


def cmd_stories_list(args: argparse.Namespace) -> int:
    data = _request("GET", f"/api/features/{args.feature}/stories", base=args.base)
    _print(data)
    return 0


def cmd_stories_get(args: argparse.Namespace) -> int:
    data = _request("GET", f"/user-stories/{args.story}", base=args.base)
    _print(data)
    return 0


def cmd_stories_analyze(args: argparse.Namespace) -> int:
    data = _request(
        "POST",
        f"/api/features/{args.feature}/stories/{args.story}/analyze",
        base=args.base,
    )
    _print(data)
    return 0


def cmd_stories_generate(args: argparse.Namespace) -> int:
    flags = assert_grounded_flags()
    story = _request("GET", f"/user-stories/{args.story}", base=args.base)
    linked = str(story.get("feature_id") or "")
    if not linked:
        raise SystemExit(
            "REFUSE: story has no feature_id. Link it first "
            f"(stories link --feature {args.feature} --story {args.story})."
        )
    if linked != str(args.feature):
        raise SystemExit(
            f"REFUSE: story.feature_id={linked} does not match --feature {args.feature}."
        )
    created = _request("POST", f"/user-stories/{args.story}/generate", base=args.base)
    _print(
        {
            "grounded_flags": flags,
            "feature_id": linked,
            "story_id": str(args.story),
            "result": created,
        }
    )
    return 0


def cmd_cases_list(args: argparse.Namespace) -> int:
    cases = fetch_story_cases(args.base, args.story)
    _print({"story_id": args.story, "cases": number_cases(cases)})
    return 0


def cmd_cases_get(args: argparse.Namespace) -> int:
    cases = fetch_story_cases(args.base, args.story)
    case_id = resolve_case_id(cases, case_id=args.case, index=args.index)
    data = _request("GET", f"/test-cases/{case_id}", base=args.base)
    _print(data)
    return 0


def cmd_cases_approve(args: argparse.Namespace) -> int:
    cases = fetch_story_cases(args.base, args.story)
    if args.all:
        drafts = [c for c in cases if str(c.get("status")) == "draft" and not c.get("stale")]
        if not drafts:
            raise SystemExit("REFUSE: no non-stale draft cases to approve. Run: cases list --story ...")
        body = {
            "user_story_id": args.story,
            "approved": [
                {
                    "test_case_id": c["id"],
                    "title": c.get("title") or "",
                    "steps": list(c.get("steps") or []),
                    "expected_result": c.get("expected_result") or "",
                    "preconditions": c.get("preconditions"),
                    "tags": list(c.get("tags") or []),
                }
                for c in drafts
            ],
        }
        data = _request("POST", "/test-cases/batch-approve", base=args.base, body=body)
        _print(data)
        return 0

    case_id = resolve_case_id(cases, case_id=args.case, index=args.index)
    row = next(c for c in cases if str(c.get("id")) == case_id)
    if row.get("stale"):
        raise SystemExit("REFUSE: case is stale; regenerate/re-approve after story change.")
    data = _request("PATCH", f"/test-cases/{case_id}", base=args.base, body={"status": "approved"})
    _print(data)
    return 0


def cmd_scripts_build(args: argparse.Namespace) -> int:
    cases = fetch_story_cases(args.base, args.story)
    approved = [c for c in cases if str(c.get("status")) == "approved" and not c.get("stale")]
    if not approved:
        raise SystemExit(
            "REFUSE: no approved non-stale cases. Approve drafts first "
            "(cases approve --story ... --all)."
        )
    data = _request("POST", f"/user-stories/{args.story}/build-scripts", base=args.base)
    _print(data)
    return 0


def cmd_scripts_show(args: argparse.Namespace) -> int:
    cases = fetch_story_cases(args.base, args.story)
    case_id = resolve_case_id(cases, case_id=args.case, index=args.index)
    data = _request("GET", f"/test-cases/{case_id}/script", base=args.base)
    _print(data)
    return 0


def cmd_orgs_list(args: argparse.Namespace) -> int:
    data = _request("GET", "/orgs", base=args.base)
    _print(data)
    return 0


def cmd_personas_list(args: argparse.Namespace) -> int:
    data = _request("GET", "/personas", base=args.base)
    _print(data)
    return 0


def cmd_runs_story(args: argparse.Namespace) -> int:
    org_id = resolve_org_id(args)
    persona_id = resolve_persona_id(args)
    cases = fetch_story_cases(args.base, args.story)
    approved = [c for c in cases if str(c.get("status")) == "approved" and not c.get("stale")]
    if not approved:
        raise SystemExit(
            "REFUSE: no approved non-stale cases to run. Approve then scripts build first."
        )
    body: dict[str, Any] = {"org_id": org_id}
    if persona_id:
        body["persona_id"] = persona_id
    data = _request("POST", f"/run/user-story/{args.story}", base=args.base, body=body)
    _print(data)
    return 0


def _consume_sse(url: str) -> tuple[int, list[dict[str, Any]]]:
    """Read SSE stream; return exit code (0 ok / 1 fail) and parsed events."""
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"}, method="GET")
    events: list[dict[str, Any]] = []
    failed = False
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            event_name = "message"
            data_lines: list[str] = []
            while True:
                raw = resp.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                    continue
                if line == "":
                    if not data_lines:
                        event_name = "message"
                        continue
                    payload_text = "\n".join(data_lines)
                    data_lines = []
                    try:
                        payload: Any = json.loads(payload_text)
                    except json.JSONDecodeError:
                        payload = payload_text
                    evt = {"event": event_name, "data": payload}
                    events.append(evt)
                    _print(evt)
                    if event_name == "done" and isinstance(payload, dict):
                        if str(payload.get("status", "")).upper() == "FAIL":
                            failed = True
                    if event_name == "summary" and isinstance(payload, dict):
                        if int(payload.get("tests_failed") or 0) > 0:
                            failed = True
                    if event_name == "error":
                        failed = True
                    event_name = "message"
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, err_body, url) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach SSE stream: {exc.reason}") from exc
    return (1 if failed else 0), events


def cmd_runs_case(args: argparse.Namespace) -> int:
    org_id = resolve_org_id(args)
    persona_id = resolve_persona_id(args)
    cases = fetch_story_cases(args.base, args.story)
    case_id = resolve_case_id(cases, case_id=args.case, index=args.index)
    query: dict[str, Any] = {"org_id": org_id}
    if persona_id:
        query["persona_id"] = persona_id
    qs = urllib.parse.urlencode(query)
    url = f"{args.base.rstrip('/')}/run/test-case/{case_id}/stream?{qs}"
    code, _events = _consume_sse(url)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feature_memory",
        description="Feature Memory CLI for IDE agents (local FastAPI).",
    )
    parser.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"API base URL (default {DEFAULT_BASE} or FEATURE_MEMORY_BASE_URL)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="GET /health")
    p_status.set_defaults(func=cmd_status)

    p_features = sub.add_parser("features", help="Feature CRUD / seed")
    fsub = p_features.add_subparsers(dest="features_cmd", required=True)

    p_fl = fsub.add_parser("list", help="List features for a project")
    p_fl.add_argument("--project", required=True)
    p_fl.add_argument("--include-archived", action="store_true")
    p_fl.set_defaults(func=cmd_features_list)

    p_fg = fsub.add_parser("get", help="Get one feature")
    p_fg.add_argument("--feature", required=True)
    p_fg.set_defaults(func=cmd_features_get)

    p_fc = fsub.add_parser("create", help="Create feature")
    p_fc.add_argument("--project", required=True)
    p_fc.add_argument("--name", required=True)
    p_fc.add_argument("--summary", default="")
    p_fc.set_defaults(func=cmd_features_create)

    p_fs = fsub.add_parser("seed", help="Apply SF Core seed (empty memory only)")
    p_fs.add_argument("--feature", required=True)
    p_fs.add_argument("--template", required=True, help="Seed template_id")
    p_fs.set_defaults(func=cmd_features_seed)

    p_st = sub.add_parser("seed-templates", help="List Salesforce seed templates")
    p_st.add_argument("--project", required=True)
    p_st.set_defaults(func=cmd_seed_templates)

    p_memory = sub.add_parser("memory", help="Feature Memory get/put/deltas")
    msub = p_memory.add_subparsers(dest="memory_cmd", required=True)

    p_mg = msub.add_parser("get", help="GET memory")
    p_mg.add_argument("--feature", required=True)
    p_mg.set_defaults(func=cmd_memory_get)

    p_mp = msub.add_parser("put", help="PUT memory facts (user-owned edits)")
    p_mp.add_argument("--feature", required=True)
    p_mp.add_argument("--file", help="JSON file: facts list or {reason,facts}")
    p_mp.add_argument("--facts-json", help="Inline JSON same shape as --file")
    p_mp.add_argument("--reason", default="manual_edit")
    p_mp.set_defaults(func=cmd_memory_put)

    p_md = msub.add_parser("deltas", help="List memory deltas")
    p_md.add_argument("--feature", required=True)
    p_md.add_argument("--status", default="pending", help="pending|accepted|rejected|all")
    p_md.set_defaults(func=cmd_memory_deltas)

    p_ma = msub.add_parser("accept", help="Accept a pending delta")
    p_ma.add_argument("--feature", required=True)
    p_ma.add_argument("--delta", required=True)
    p_ma.add_argument("--reason", default="delta_accepted")
    p_ma.set_defaults(func=cmd_memory_accept)

    p_mr = msub.add_parser("reject", help="Reject a pending delta")
    p_mr.add_argument("--feature", required=True)
    p_mr.add_argument("--delta", required=True)
    p_mr.add_argument("--reason", default="delta_rejected")
    p_mr.set_defaults(func=cmd_memory_reject)

    p_rq = sub.add_parser("review-queue", help="Unmatched stories + match conflicts")
    p_rq.add_argument("--project", required=True)
    p_rq.set_defaults(func=cmd_review_queue)

    p_rules = sub.add_parser("match-rules", help="Epic/label/component to feature maps")
    rsub = p_rules.add_subparsers(dest="match_cmd", required=True)

    p_rl = rsub.add_parser("list", help="List match rules")
    p_rl.add_argument("--project", required=True)
    p_rl.set_defaults(func=cmd_match_rules_list)

    p_rs = rsub.add_parser("set", help="Upsert a match rule")
    p_rs.add_argument("--project", required=True)
    p_rs.add_argument("--kind", required=True, choices=["epic", "label", "component"])
    p_rs.add_argument("--key", required=True)
    p_rs.add_argument("--feature", required=True)
    p_rs.set_defaults(func=cmd_match_rules_set)

    p_stories = sub.add_parser("stories", help="Link / analyze / grounded generate")
    ssub = p_stories.add_subparsers(dest="stories_cmd", required=True)

    p_sl = ssub.add_parser("link", help="Link story to feature")
    p_sl.add_argument("--feature", required=True)
    p_sl.add_argument("--story", required=True)
    p_sl.set_defaults(func=cmd_stories_link)

    p_slist = ssub.add_parser("list", help="List stories on a feature")
    p_slist.add_argument("--feature", required=True)
    p_slist.set_defaults(func=cmd_stories_list)

    p_sg = ssub.add_parser("get", help="GET /user-stories/{id}")
    p_sg.add_argument("--story", required=True)
    p_sg.set_defaults(func=cmd_stories_get)

    p_sa = ssub.add_parser("analyze", help="Feature-scoped analyze (propose deltas)")
    p_sa.add_argument("--feature", required=True)
    p_sa.add_argument("--story", required=True)
    p_sa.set_defaults(func=cmd_stories_analyze)

    p_sgen = ssub.add_parser(
        "generate",
        help="Grounded TC generate (forces feature_memory_only / no RAG / no catalog)",
    )
    p_sgen.add_argument("--story", required=True)
    p_sgen.add_argument("--feature", required=True)
    p_sgen.set_defaults(func=cmd_stories_generate)

    p_cases = sub.add_parser("cases", help="List / get / approve test cases")
    csub = p_cases.add_subparsers(dest="cases_cmd", required=True)

    p_cl = csub.add_parser("list", help="Numbered cases for a story (TC N = index N)")
    p_cl.add_argument("--story", required=True)
    p_cl.set_defaults(func=cmd_cases_list)

    p_cg = csub.add_parser("get", help="Get one case by --case or --index")
    p_cg.add_argument("--story", required=True)
    p_cg.add_argument("--case", default=None)
    p_cg.add_argument("--index", type=int, default=None)
    p_cg.set_defaults(func=cmd_cases_get)

    p_ca = csub.add_parser("approve", help="Approve one case or all drafts")
    p_ca.add_argument("--story", required=True)
    p_ca.add_argument("--case", default=None)
    p_ca.add_argument("--index", type=int, default=None)
    p_ca.add_argument("--all", action="store_true", help="Approve all non-stale drafts")
    p_ca.set_defaults(func=cmd_cases_approve)

    p_scripts = sub.add_parser("scripts", help="Build / show Robot scripts")
    scsub = p_scripts.add_subparsers(dest="scripts_cmd", required=True)

    p_sb = scsub.add_parser("build", help="POST build-scripts for approved cases")
    p_sb.add_argument("--story", required=True)
    p_sb.set_defaults(func=cmd_scripts_build)

    p_ss = scsub.add_parser("show", help="GET saved .robot for one case")
    p_ss.add_argument("--story", required=True)
    p_ss.add_argument("--case", default=None)
    p_ss.add_argument("--index", type=int, default=None)
    p_ss.set_defaults(func=cmd_scripts_show)

    p_orgs = sub.add_parser("orgs", help="Salesforce orgs")
    osub = p_orgs.add_subparsers(dest="orgs_cmd", required=True)
    p_ol = osub.add_parser("list", help="GET /orgs")
    p_ol.set_defaults(func=cmd_orgs_list)

    p_personas = sub.add_parser("personas", help="Personas")
    psub = p_personas.add_subparsers(dest="personas_cmd", required=True)
    p_pl = psub.add_parser("list", help="GET /personas")
    p_pl.set_defaults(func=cmd_personas_list)

    p_runs = sub.add_parser("runs", help="Execute Robot for story or one case")
    rrun = p_runs.add_subparsers(dest="runs_cmd", required=True)

    p_rs = rrun.add_parser("story", help="POST /run/user-story/{id}")
    p_rs.add_argument("--story", required=True)
    p_rs.add_argument("--org", default=None, help=f"or FEATURE_MEMORY_ORG_ID ({DEFAULT_ORG or 'unset'})")
    p_rs.add_argument("--persona", default=None, help="or FEATURE_MEMORY_PERSONA_ID")
    p_rs.set_defaults(func=cmd_runs_story)

    p_rc = rrun.add_parser("case", help="SSE /run/test-case/{id}/stream")
    p_rc.add_argument("--story", required=True)
    p_rc.add_argument("--case", default=None)
    p_rc.add_argument("--index", type=int, default=None)
    p_rc.add_argument("--org", default=None, help="or FEATURE_MEMORY_ORG_ID")
    p_rc.add_argument("--persona", default=None, help="or FEATURE_MEMORY_PERSONA_ID")
    p_rc.set_defaults(func=cmd_runs_case)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ApiError as exc:
        print(json.dumps({"error": True, "status": exc.status, "url": exc.url, "body": exc.body}, indent=2))
        return 1
    except ValueError as exc:
        print(json.dumps({"error": True, "message": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
