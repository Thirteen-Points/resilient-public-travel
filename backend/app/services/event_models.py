"""Contract models for disruption events.

The fields mirror ``docs/plan/03-contracts.md``.  ``line`` and ``direction``
remain non-empty strings because the contract currently gives examples but no
consistent enum for them (the documented line enum and Event example differ).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EventStatus = Literal[
    "draft",
    "pending_review",
    "published",
    "updated",
    "expired",
    "rejected",
]
EventType = Literal[
    "signal_failure",
    "train_failure",
    "door_fault",
    "power_failure",
    "weather",
    "crowd",
    "road_incident",
    "other",
]
TransportMode = Literal["MTR", "BUS", "MINIBUS", "WALK", "FERRY"]
ImpactType = Literal["closed", "reduced_capacity", "slow", "crowded"]
Provenance = Literal["real", "real-derived", "simulated"]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class ContractModel(BaseModel):
    """Strict base model used by every Event sub-object."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AffectedSegment(ContractModel):
    from_node: str
    to_node: str
    impact: ImpactType
    capacity_factor: Probability

    @field_validator("from_node", "to_node")
    @classmethod
    def node_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("node id must not be empty")
        return value


class EventWindow(ContractModel):
    start: datetime
    end: datetime | None
    end_confidence: str

    @field_validator("end_confidence")
    @classmethod
    def end_confidence_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("end_confidence must not be empty")
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "EventWindow":
        if self.end is not None and self.end < self.start:
            raise ValueError("window end must not be before start")
        return self


class ConfidenceFactor(ContractModel):
    factor: str
    weight: Probability
    score: Probability
    note: str


class AuditEntry(ContractModel):
    at: datetime
    actor: str
    action: str
    confidence_after: Probability

    @field_validator("actor", "action")
    @classmethod
    def audit_text_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("audit actor and action must not be empty")
        return value


class Event(ContractModel):
    """The Event contract shared by B's pipeline, A's UI and C's engine."""

    event_id: str
    version: int = Field(ge=1)
    status: EventStatus
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    expires_at: datetime | None

    event_type: EventType
    title: str
    summary: str

    mode: TransportMode
    line: str
    direction: str
    affected_segments: list[AffectedSegment]
    window: EventWindow
    severity: int = Field(ge=1, le=5)

    confidence: Probability
    confidence_factors: list[ConfidenceFactor]

    signals: list[str]
    reviewed_by: str | None
    audit_log: list[AuditEntry] = Field(default_factory=list)
    provenance: Provenance

    @field_validator("event_id", "title", "summary", "line", "direction")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("required text must not be empty")
        return value

    @model_validator(mode="after")
    def timestamps_are_consistent(self) -> "Event":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be before created_at")
        if self.published_at is not None and self.published_at < self.created_at:
            raise ValueError("published_at must not be before created_at")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at must not be before created_at")
        return self
