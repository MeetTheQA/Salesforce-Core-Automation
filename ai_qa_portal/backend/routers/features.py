"""Feature Knowledge Brain endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai_qa_portal.backend.config import settings
from ai_qa_portal.backend.models.feature import (
    Feature,
    FeatureCreate,
    FeatureMemory,
    FeatureMemoryDelta,
    FeatureMemoryFact,
    FeatureStatus,
    FeatureUpdate,
)
from ai_qa_portal.backend.models.user_story import UserStory
from ai_qa_portal.backend.services.access import require_project_access
from ai_qa_portal.backend.services.auth import get_current_user
from ai_qa_portal.backend.services.db import ProjectRole, User, get_db
from ai_qa_portal.backend.services.feature_memory import (
    build_grounded_context,
    create_delta,
    load_feature_memory,
    parse_json_object,
    upsert_memory_facts,
)
from ai_qa_portal.backend.services.feature_matcher import (
    delete_match_rule,
    list_match_rules,
    upsert_match_rule,
)
from ai_qa_portal.backend.services.prompt_seeds import read_seed_body
from ai_qa_portal.backend.services.salesforce_feature_seeds import (
    facts_for_template,
    list_seed_templates,
)
from ai_qa_portal.backend.storage.json_file_backend import JsonFileBackend

_store = JsonFileBackend(settings.data_dir)

router = APIRouter(
    prefix="/api/features",
    tags=["features"],
    dependencies=[Depends(get_current_user)],
)


class MemoryFactInput(BaseModel):
    section: str
    text: str
    source_kind: str
    source_story_keys: list[str] = Field(default_factory=list)
    source_note: str | None = None


class MemoryEditRequest(BaseModel):
    reason: str = "manual_edit"
    facts: list[MemoryFactInput]


class AnalyzeResponse(BaseModel):
    story_id: str
    feature_id: str
    analysis_markdown: str
    delta_id: str
    facts_proposed: int


class MergeRequest(BaseModel):
    project_id: UUID
    target_feature_id: UUID
    source_feature_id: UUID


class DeltaActionRequest(BaseModel):
    reason: str = "manual_review"


def _load_feature_or_404(feature_id: UUID) -> Feature:
    try:
        row = _store.get_feature(feature_id)
    except KeyError as exc:
        raise HTTPException(404, "Feature not found") from exc
    return Feature.model_validate(row)


def _load_story_or_404(story_id: UUID) -> UserStory:
    try:
        row = _store.get_user_story(story_id)
    except KeyError as exc:
        raise HTTPException(404, "User story not found") from exc
    return UserStory.model_validate(row)


def _assert_project_access(db: Session, user: User, project_id: UUID, role: ProjectRole = ProjectRole.member) -> None:
    require_project_access(db, user, str(project_id), role=role)


def _story_key(story: UserStory) -> str:
    payload = story.external_payload or {}
    key = str(payload.get("key") or story.external_id or "").strip()
    return key or str(story.id)


@router.post("", response_model=Feature, status_code=201)
def create_feature(
    body: FeatureCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, body.project_id, ProjectRole.lead)
    now = datetime.now(UTC)
    feature = Feature(
        id=uuid4(),
        project_id=body.project_id,
        name=(body.name or "").strip() or "Untitled feature",
        summary=(body.summary or "").strip(),
        status=FeatureStatus.active,
        created_at=now,
        updated_at=now,
        owner_user_id=current_user.id,
    )
    _store.save_feature(feature.model_dump(mode="json"))
    return feature


@router.get("", response_model=list[Feature])
def list_features(
    project_id: UUID = Query(...),
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, project_id)
    rows = [Feature.model_validate(r) for r in _store.list_features(project_id)]
    if not include_archived:
        rows = [r for r in rows if r.status == FeatureStatus.active]
    rows.sort(key=lambda r: r.updated_at, reverse=True)
    return rows


class MatchRuleWrite(BaseModel):
    project_id: UUID
    kind: str
    key: str
    feature_id: UUID


class MatchRuleDelete(BaseModel):
    project_id: UUID
    kind: str
    key: str


class SeedApplyRequest(BaseModel):
    template_id: str


@router.get("/match-rules")
def get_match_rules(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, project_id)
    return {"rules": list_match_rules(_store, project_id)}


@router.post("/match-rules")
def put_match_rule(
    body: MatchRuleWrite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, body.project_id, ProjectRole.lead)
    feature = _load_feature_or_404(body.feature_id)
    if feature.project_id != body.project_id:
        raise HTTPException(422, "Feature is not in this project")
    try:
        return upsert_match_rule(
            _store,
            body.project_id,
            kind=body.kind.strip().lower(),
            raw_key=body.key,
            feature_id=str(body.feature_id),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/match-rules")
def remove_match_rule(
    body: MatchRuleDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, body.project_id, ProjectRole.lead)
    delete_match_rule(
        _store,
        body.project_id,
        kind=body.kind.strip().lower(),
        raw_key=body.key,
    )
    return {"ok": True}


@router.get("/seed-templates")
def get_seed_templates(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, project_id)
    return {"templates": list_seed_templates()}


@router.get("/review-queue")
def feature_review_queue(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, project_id)
    stories = [UserStory.model_validate(r) for r in _store.list_user_stories(project_id)]
    unmatched = [
        {"id": str(s.id), "title": s.title, "external_id": s.external_id}
        for s in stories
        if s.feature_id is None and s.status.value == "active"
    ]
    return {
        "unmatched": unmatched,
        "conflicts": _store.list_feature_match_conflicts(project_id),
    }


@router.get("/{feature_id}", response_model=Feature)
def get_feature(
    feature_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id)
    return feature


@router.patch("/{feature_id}", response_model=Feature)
def update_feature(
    feature_id: UUID,
    body: FeatureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    row = _store.get_feature(feature_id)
    if body.name is not None:
        row["name"] = body.name.strip() or row.get("name") or "Untitled feature"
    if body.summary is not None:
        row["summary"] = body.summary.strip()
    if body.status is not None:
        row["status"] = body.status.value
    row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_feature(row)
    return Feature.model_validate(row)


@router.post("/{feature_id}/seed", response_model=FeatureMemory)
def apply_feature_seed(
    feature_id: UUID,
    body: SeedApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    memory = load_feature_memory(_store, feature_id)
    if memory.facts:
        raise HTTPException(409, "Seed applies only when feature memory is empty")
    try:
        facts = facts_for_template(body.template_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown seed template") from exc
    return upsert_memory_facts(
        _store,
        feature_id,
        incoming_facts=facts,
        reason=f"seed_template:{body.template_id}",
        author_user_id=current_user.id,
    )


@router.get("/{feature_id}/stories", response_model=list[UserStory])
def list_feature_stories(
    feature_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id)
    rows = [UserStory.model_validate(r) for r in _store.get_user_stories_by_feature(feature_id)]
    rows.sort(key=lambda r: r.updated_at, reverse=True)
    return rows


@router.post("/{feature_id}/stories/{story_id}", response_model=UserStory)
def link_story_to_feature(
    feature_id: UUID,
    story_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    story = _load_story_or_404(story_id)
    if story.project_id != feature.project_id:
        raise HTTPException(422, "Story and Feature project_id mismatch")
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    row = _store.get_user_story(story_id)
    row["feature_id"] = str(feature_id)
    row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_user_story(row)
    return UserStory.model_validate(row)


@router.delete("/{feature_id}/stories/{story_id}", response_model=UserStory)
def unlink_story_from_feature(
    feature_id: UUID,
    story_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    story = _load_story_or_404(story_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    if str(story.feature_id or "") != str(feature_id):
        raise HTTPException(409, "Story is not linked to this feature")
    row = _store.get_user_story(story_id)
    row["feature_id"] = None
    row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_user_story(row)
    return UserStory.model_validate(row)


@router.post("/merge", response_model=dict[str, Any])
def merge_features(
    body: MergeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_project_access(db, current_user, body.project_id, ProjectRole.lead)
    if body.target_feature_id == body.source_feature_id:
        raise HTTPException(422, "target and source must differ")
    target = _load_feature_or_404(body.target_feature_id)
    source = _load_feature_or_404(body.source_feature_id)
    if target.project_id != body.project_id or source.project_id != body.project_id:
        raise HTTPException(422, "feature project mismatch")
    moved = 0
    for row in _store.get_user_stories_by_feature(body.source_feature_id):
        row["feature_id"] = str(body.target_feature_id)
        row["updated_at"] = datetime.now(UTC).isoformat()
        _store.save_user_story(row)
        moved += 1
    source_mem = load_feature_memory(_store, body.source_feature_id)
    if source_mem.facts:
        upsert_memory_facts(
            _store,
            body.target_feature_id,
            incoming_facts=source_mem.facts,
            reason=f"merge_feature:{body.source_feature_id}",
            author_user_id=current_user.id,
        )
    src_row = _store.get_feature(body.source_feature_id)
    src_row["status"] = FeatureStatus.archived.value
    src_row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_feature(src_row)
    return {"ok": True, "moved_stories": moved, "source_archived": str(body.source_feature_id)}


@router.get("/{feature_id}/memory", response_model=FeatureMemory)
def get_feature_memory(
    feature_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id)
    return load_feature_memory(_store, feature_id)


@router.put("/{feature_id}/memory", response_model=FeatureMemory)
def edit_feature_memory(
    feature_id: UUID,
    body: MemoryEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    incoming: list[FeatureMemoryFact] = []
    now = datetime.now(UTC)
    for f in body.facts:
        incoming.append(
            FeatureMemoryFact(
                id=str(uuid4()),
                section=f.section.strip(),
                text=f.text.strip(),
                source_kind=f.source_kind.strip(),
                source_story_keys=list(dict.fromkeys([x.strip() for x in f.source_story_keys if x.strip()])),
                source_note=(f.source_note or "").strip() or None,
                created_at=now,
                updated_at=now,
            ),
        )
    return upsert_memory_facts(
        _store,
        feature_id,
        incoming_facts=incoming,
        reason=body.reason or "manual_edit",
        author_user_id=current_user.id,
    )


@router.get("/{feature_id}/memory/revisions", response_model=list[dict[str, Any]])
def list_memory_revisions(
    feature_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id)
    return _store.list_feature_memory_revisions(feature_id)


@router.get("/{feature_id}/memory/deltas", response_model=list[FeatureMemoryDelta])
def list_memory_deltas(
    feature_id: UUID,
    status: str = Query("pending"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id)
    rows = [FeatureMemoryDelta.model_validate(r) for r in _store.list_feature_memory_deltas(feature_id)]
    if status != "all":
        rows = [r for r in rows if r.status.value == status]
    rows.sort(key=lambda r: r.updated_at, reverse=True)
    return rows


@router.post("/{feature_id}/memory/deltas/{delta_id}/accept", response_model=FeatureMemory)
def accept_memory_delta(
    feature_id: UUID,
    delta_id: str,
    body: DeltaActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    row = _store.get_feature_memory_delta(delta_id)
    delta = FeatureMemoryDelta.model_validate(row)
    if str(delta.feature_id) != str(feature_id):
        raise HTTPException(409, "Delta does not belong to this feature")
    if delta.status.value != "pending":
        raise HTTPException(409, f"Delta already {delta.status.value}")
    memory = upsert_memory_facts(
        _store,
        feature_id,
        incoming_facts=delta.facts,
        reason=body.reason or "delta_accepted",
        author_user_id=current_user.id,
    )
    row["status"] = "accepted"
    row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_feature_memory_delta(row)
    return memory


@router.post("/{feature_id}/memory/deltas/{delta_id}/reject", response_model=FeatureMemoryDelta)
def reject_memory_delta(
    feature_id: UUID,
    delta_id: str,
    _body: DeltaActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    _assert_project_access(db, current_user, feature.project_id, ProjectRole.lead)
    row = _store.get_feature_memory_delta(delta_id)
    delta = FeatureMemoryDelta.model_validate(row)
    if str(delta.feature_id) != str(feature_id):
        raise HTTPException(409, "Delta does not belong to this feature")
    row["status"] = "rejected"
    row["updated_at"] = datetime.now(UTC).isoformat()
    _store.save_feature_memory_delta(row)
    return FeatureMemoryDelta.model_validate(row)


@router.post("/{feature_id}/stories/{story_id}/analyze", response_model=AnalyzeResponse)
async def analyze_story_with_feature_memory(
    feature_id: UUID,
    story_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature = _load_feature_or_404(feature_id)
    story = _load_story_or_404(story_id)
    if str(story.feature_id or "") != str(feature_id):
        raise HTTPException(409, "Story must be linked to this feature before analysis")
    _assert_project_access(db, current_user, feature.project_id)
    memory = load_feature_memory(_store, feature_id)
    related = [
        UserStory.model_validate(r)
        for r in _store.get_user_stories_by_feature(feature_id)
        if str(r.get("id")) != str(story_id)
    ]
    context = build_grounded_context(story=story, memory=memory, related_stories=related, analysis_text=None)
    try:
        system_prompt = read_seed_body("grounded_requirement_analyzer.md")
    except FileNotFoundError:
        system_prompt = (
            "You are a senior Salesforce QA analyst. Use ONLY provided facts. "
            "Return ONLY JSON with analysis_markdown and proposed_facts."
        )
    user_prompt = (
        f"{context}\n\n"
        "Produce requirement analysis sections: Goal, In scope, Out of scope, Assumptions, Risks, Clarifications needed.\n"
        "Then propose durable memory facts only."
    )
    from ai_bridge import call_llm_with_metadata

    llm_result = await asyncio.to_thread(call_llm_with_metadata, system_prompt, user_prompt)
    parsed = parse_json_object(llm_result.text)
    analysis_md = str(parsed.get("analysis_markdown") or "").strip()
    raw_facts = parsed.get("proposed_facts") or []
    story_key = _story_key(story)
    now = datetime.now(UTC)
    facts: list[FeatureMemoryFact] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        section = str(item.get("section") or "").strip().lower().replace(" ", "_")
        if not text or not section:
            continue
        facts.append(
            FeatureMemoryFact(
                id=str(uuid4()),
                section=section,
                text=text,
                source_kind="analysis",
                source_story_keys=[story_key],
                source_note=None,
                created_at=now,
                updated_at=now,
            ),
        )
    delta = create_delta(
        _store,
        feature_id=feature_id,
        story_id=story_id,
        source="analysis",
        facts=facts,
        notes=analysis_md[:4000],
    )
    _store.write(
        f"story_analysis:{story_id}",
        {
            "story_id": str(story_id),
            "feature_id": str(feature_id),
            "analysis_markdown": analysis_md,
            "delta_id": delta.id,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    return AnalyzeResponse(
        story_id=str(story_id),
        feature_id=str(feature_id),
        analysis_markdown=analysis_md,
        delta_id=delta.id,
        facts_proposed=len(facts),
    )
