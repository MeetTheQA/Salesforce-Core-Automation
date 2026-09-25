from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ai_qa_portal.backend.models.feature import (
    FeatureMemory,
    FeatureMemoryDelta,
    FeatureMemoryDeltaStatus,
    FeatureMemoryFact,
    FeatureMemoryRevision,
)
from ai_qa_portal.backend.models.user_story import UserStory
from ai_qa_portal.backend.storage.json_file_backend import JsonFileBackend


SECTION_ORDER = [
    "summary",
    "business_rules",
    "salesforce_objects",
    "fields",
    "permissions",
    "validation",
    "automation",
    "integrations",
    "known_risks",
    "open_questions",
    "testing_notes",
]


def load_feature_memory(store: JsonFileBackend, feature_id: UUID) -> FeatureMemory:
    row = store.get_feature_memory(feature_id)
    if row:
        return FeatureMemory.model_validate(row)
    return FeatureMemory(
        feature_id=feature_id,
        version=1,
        markdown="",
        facts=[],
        updated_at=datetime.now(UTC),
    )


def render_feature_memory_markdown(memory: FeatureMemory) -> str:
    grouped: dict[str, list[FeatureMemoryFact]] = {}
    for fact in memory.facts:
        grouped.setdefault(fact.section, []).append(fact)
    lines: list[str] = []
    for section in SECTION_ORDER:
        items = grouped.get(section, [])
        if not items:
            continue
        title = section.replace("_", " ").title()
        lines.append(f"## {title}")
        for fact in items:
            source = fact.source_note or ",".join(fact.source_story_keys)
            src_suffix = f" _(source: {fact.source_kind}: {source})_" if source else ""
            lines.append(f"- {fact.text}{src_suffix}")
        lines.append("")
    if not lines:
        return ""
    return "\n".join(lines).strip()


def _fact_dedupe_key(fact: FeatureMemoryFact) -> tuple[str, str]:
    return (fact.section.strip().lower(), fact.text.strip().lower())


def validate_fact(fact: FeatureMemoryFact) -> None:
    kind = (fact.source_kind or "").strip().lower()
    if kind not in {"jira_story", "analysis", "user"}:
        raise ValueError("source_kind must be jira_story, analysis, or user")
    if kind in {"jira_story", "analysis"} and not fact.source_story_keys:
        raise ValueError("jira_story/analysis facts require source_story_keys")
    if kind == "user" and not (fact.source_note or "").strip():
        raise ValueError("user facts require source_note")


def upsert_memory_facts(
    store: JsonFileBackend,
    feature_id: UUID,
    *,
    incoming_facts: list[FeatureMemoryFact],
    reason: str,
    author_user_id: str,
) -> FeatureMemory:
    memory = load_feature_memory(store, feature_id)
    existing_map = {_fact_dedupe_key(f): f for f in memory.facts}
    for incoming in incoming_facts:
        validate_fact(incoming)
        key = _fact_dedupe_key(incoming)
        now = datetime.now(UTC)
        if key in existing_map:
            prev = existing_map[key]
            prev.source_kind = incoming.source_kind
            prev.source_story_keys = list(dict.fromkeys(incoming.source_story_keys))
            prev.source_note = incoming.source_note
            prev.updated_at = now
        else:
            incoming.created_at = now
            incoming.updated_at = now
            memory.facts.append(incoming)
            existing_map[key] = incoming
    memory.version = int(memory.version or 1) + 1
    memory.updated_at = datetime.now(UTC)
    memory.markdown = render_feature_memory_markdown(memory)
    store.save_feature_memory(feature_id, memory.model_dump(mode="json"))
    revision = FeatureMemoryRevision(
        id=str(uuid4()),
        feature_id=feature_id,
        version=memory.version,
        reason=reason,
        author_user_id=author_user_id,
        created_at=datetime.now(UTC),
        memory=memory,
    )
    store.append_feature_memory_revision(feature_id, revision.model_dump(mode="json"))
    return memory


def create_delta(
    store: JsonFileBackend,
    *,
    feature_id: UUID,
    facts: list[FeatureMemoryFact],
    source: str,
    story_id: UUID | None = None,
    notes: str = "",
) -> FeatureMemoryDelta:
    now = datetime.now(UTC)
    delta = FeatureMemoryDelta(
        id=str(uuid4()),
        feature_id=feature_id,
        story_id=story_id,
        status=FeatureMemoryDeltaStatus.pending,
        created_at=now,
        updated_at=now,
        source=source,
        facts=facts,
        notes=notes,
    )
    store.save_feature_memory_delta(delta.model_dump(mode="json"))
    return delta


def build_grounded_context(
    *,
    story: UserStory,
    memory: FeatureMemory,
    related_stories: list[UserStory],
    analysis_text: str | None,
) -> str:
    rel_lines: list[str] = []
    for s in related_stories[:8]:
        title = (s.title or "").strip()[:200]
        desc = (s.description or "").strip()[:2000]
        rel_lines.append(f"- {title}\n{desc}")
    related_block = "\n".join(rel_lines) if rel_lines else "None"
    memory_md = (memory.markdown or "").strip()[:12000] or "None"
    analysis_block = (analysis_text or "").strip()[:12000] or "None"
    return (
        "## Current story\n"
        f"Title: {story.title}\n\n"
        f"{story.description.strip()}\n\n"
        "## Feature memory (authoritative)\n"
        f"{memory_md}\n\n"
        "## Related stories in this feature\n"
        f"{related_block}\n\n"
        "## Requirement analysis (latest)\n"
        f"{analysis_block}\n"
    )


def parse_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty LLM output")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("could not parse JSON object")
    obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("LLM output JSON is not an object")
    return obj

