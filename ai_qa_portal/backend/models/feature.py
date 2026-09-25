from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeatureStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class Feature(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    summary: str = ""
    status: FeatureStatus = FeatureStatus.active
    created_at: datetime
    updated_at: datetime
    owner_user_id: str = ""


class FeatureCreate(BaseModel):
    project_id: UUID
    name: str
    summary: str = ""


class FeatureUpdate(BaseModel):
    name: str | None = None
    summary: str | None = None
    status: FeatureStatus | None = None


class FeatureMemoryFact(BaseModel):
    id: str
    section: str
    text: str
    source_kind: str
    source_story_keys: list[str] = Field(default_factory=list)
    source_note: str | None = None
    created_at: datetime
    updated_at: datetime


class FeatureMemory(BaseModel):
    feature_id: UUID
    version: int = 1
    markdown: str = ""
    facts: list[FeatureMemoryFact] = Field(default_factory=list)
    updated_at: datetime


class FeatureMemoryRevision(BaseModel):
    id: str
    feature_id: UUID
    version: int
    reason: str
    author_user_id: str = ""
    created_at: datetime
    memory: FeatureMemory


class FeatureMemoryDeltaStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class FeatureMemoryDelta(BaseModel):
    id: str
    feature_id: UUID
    story_id: UUID | None = None
    status: FeatureMemoryDeltaStatus = FeatureMemoryDeltaStatus.pending
    created_at: datetime
    updated_at: datetime
    source: str = ""
    facts: list[FeatureMemoryFact] = Field(default_factory=list)
    notes: str = ""

