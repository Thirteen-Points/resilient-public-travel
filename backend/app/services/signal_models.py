"""Contract model for raw signals entering the event pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from .event_models import Provenance


class Signal(BaseModel):
    """Raw, unstructured signal defined by ``03-contracts.md`` section 3.1."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    signal_id: str
    received_at: datetime
    source_type: str
    source_name: str
    author_hint: str | None
    raw_text: str
    raw_url: str | None
    lang: str
    provenance: Provenance

    @field_validator(
        "signal_id",
        "source_type",
        "source_name",
        "raw_text",
        "lang",
    )
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("required Signal text must not be empty")
        return value
