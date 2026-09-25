"""Deterministic story → feature matching.

Epic, label, and component rules only. No LLM. A single agreeing
feature is a match. Disagreement is a conflict and the story stays
unlinked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ai_qa_portal.backend.storage.json_file_backend import JsonFileBackend

MATCH_KINDS = ("epic", "label", "component")


def normalize_token(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_variants(value: str) -> set[str]:
    base = normalize_token(value)
    if not base:
        return set()
    variants = {base}
    if base.endswith("s") and len(base) > 4 and not base.endswith("ss"):
        variants.add(base[:-1])
    elif not base.endswith("s"):
        variants.add(f"{base}s")
    return variants


@dataclass
class MatchSignals:
    epic_keys: list[str] = field(default_factory=list)
    epic_names: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    status: str  # matched | unmatched | conflict
    feature_id: str | None = None
    reason: str = ""
    hits: list[dict[str, str]] = field(default_factory=list)


def extract_match_signals(payload: dict[str, Any] | None, labels: list | None = None) -> MatchSignals:
    fields = (payload or {}).get("fields") or {}
    parent = fields.get("parent") or {}
    parent_fields = parent.get("fields") or {}
    epic_keys: list[str] = []
    epic_names: list[str] = []
    if parent.get("key"):
        epic_keys.append(str(parent.get("key")))
    summary = parent_fields.get("summary")
    if summary:
        epic_names.append(str(summary))
    for key, val in fields.items():
        if not str(key).lower().startswith("customfield_"):
            continue
        if isinstance(val, str) and re.match(r"^[A-Z][A-Z0-9]+-\d+$", val.strip()):
            epic_keys.append(val.strip())
    raw_labels = fields.get("labels") if isinstance(fields.get("labels"), list) else (labels or [])
    components = []
    for comp in fields.get("components") or []:
        if isinstance(comp, dict) and comp.get("name"):
            components.append(str(comp["name"]))
        elif isinstance(comp, str):
            components.append(comp)
    return MatchSignals(
        epic_keys=[str(x) for x in epic_keys if str(x).strip()],
        epic_names=[str(x) for x in epic_names if str(x).strip()],
        labels=[str(x) for x in (raw_labels or []) if str(x).strip()],
        components=components,
    )


def _lookup(rules: dict[str, str], raw: str) -> str | None:
    for variant in token_variants(raw):
        hit = rules.get(variant)
        if hit:
            return hit
    return None


def match_signals(signals: MatchSignals, maps: dict[str, dict[str, str]]) -> MatchResult:
    hits: list[dict[str, str]] = []
    epic_rules = maps.get("epic") or {}
    label_rules = maps.get("label") or {}
    component_rules = maps.get("component") or {}

    for raw in [*signals.epic_keys, *signals.epic_names]:
        fid = _lookup(epic_rules, raw)
        if fid:
            hits.append({"kind": "epic", "value": raw, "feature_id": fid})
    for raw in signals.labels:
        fid = _lookup(label_rules, raw)
        if fid:
            hits.append({"kind": "label", "value": raw, "feature_id": fid})
    for raw in signals.components:
        fid = _lookup(component_rules, raw)
        if fid:
            hits.append({"kind": "component", "value": raw, "feature_id": fid})

    if not hits:
        return MatchResult(status="unmatched", reason="no_rule")

    feature_ids = {h["feature_id"] for h in hits}
    if len(feature_ids) > 1:
        return MatchResult(
            status="conflict",
            reason="rules_disagree",
            hits=hits,
        )
    return MatchResult(
        status="matched",
        feature_id=next(iter(feature_ids)),
        reason="deterministic_rule",
        hits=hits,
    )


def load_match_maps(store: JsonFileBackend, project_id: UUID) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for kind in MATCH_KINDS:
        row = store.get_feature_match_map(project_id, kind)
        out[kind] = {str(k): str(v) for k, v in (row.get("rules") or {}).items()}
    return out


def upsert_match_rule(
    store: JsonFileBackend,
    project_id: UUID,
    *,
    kind: str,
    raw_key: str,
    feature_id: str,
) -> dict[str, Any]:
    if kind not in MATCH_KINDS:
        raise ValueError("kind must be epic, label, or component")
    canonical = normalize_token(raw_key)
    if not canonical:
        raise ValueError("mapping key is empty")
    row = store.get_feature_match_map(project_id, kind)
    rules = dict(row.get("rules") or {})
    display = dict(row.get("display") or {})
    for variant in token_variants(raw_key):
        rules[variant] = feature_id
    display[canonical] = raw_key.strip()
    row["rules"] = rules
    row["display"] = display
    store.save_feature_match_map(project_id, kind, row)
    return {"kind": kind, "key": raw_key.strip(), "normalized": canonical, "feature_id": feature_id}


def delete_match_rule(store: JsonFileBackend, project_id: UUID, *, kind: str, raw_key: str) -> None:
    row = store.get_feature_match_map(project_id, kind)
    rules = dict(row.get("rules") or {})
    display = dict(row.get("display") or {})
    for variant in token_variants(raw_key):
        rules.pop(variant, None)
    display.pop(normalize_token(raw_key), None)
    row["rules"] = rules
    row["display"] = display
    store.save_feature_match_map(project_id, kind, row)


def list_match_rules(store: JsonFileBackend, project_id: UUID) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for kind in MATCH_KINDS:
        row = store.get_feature_match_map(project_id, kind)
        display = row.get("display") or {}
        rules = row.get("rules") or {}
        seen: set[str] = set()
        for normalized, label in display.items():
            fid = rules.get(normalized)
            if not fid or normalized in seen:
                continue
            seen.add(normalized)
            out.append({
                "kind": kind,
                "key": str(label),
                "normalized": str(normalized),
                "feature_id": str(fid),
            })
    return out


def record_conflict(
    store: JsonFileBackend,
    *,
    project_id: UUID,
    story_id: str,
    result: MatchResult,
) -> None:
    store.append_feature_match_conflict(
        project_id,
        {
            "story_id": story_id,
            "reason": result.reason,
            "hits": result.hits,
            "recorded_at": datetime.now(UTC).isoformat(),
        },
    )
