"""Internal source records; public Signal contracts remain unchanged."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from ..signal_models import Signal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SourcePost:
    platform: str
    post_id: str
    text: str
    url: str
    lang: str
    published_at: datetime | None
    author_hint: str | None
    source_name: str
    official: bool = False
    provenance: str = "real"
    repost_of: tuple[str, ...] = ()
    original: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.platform or not self.post_id or not self.url:
            raise ValueError("source identity and URL are required")
        if self.published_at is not None and (
            self.published_at.tzinfo is None or self.published_at.utcoffset() is None
        ):
            raise ValueError("publication time must be timezone-aware")

    @property
    def revision(self) -> str:
        # Formatting/clock changes alone do not manufacture new evidence.
        content = json.dumps([self.text, self.repost_of], ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()

    def to_signal(self, received_at: datetime) -> Signal:
        identity = hashlib.sha256(
            f"{self.platform}\0{self.post_id}\0{self.revision}".encode()
        ).hexdigest()
        return Signal(
            signal_id=f"online-{self.platform}-{identity}", received_at=received_at,
            source_type="official" if self.official else "social",
            source_name=self.source_name, author_hint=self.author_hint,
            raw_text=self.text, raw_url=self.url, lang=self.lang,
            provenance=self.provenance,
        )


def anonymous_author(platform: str, author_id: str | None, secret: str) -> str | None:
    """Stable pseudonym; secret is environment-only, never stored or logged."""
    if not author_id:
        return None
    if len(secret) < 32:
        raise ValueError("INGEST_AUTHOR_SALT must contain at least 32 characters")
    digest = hmac.new(secret.encode(), f"{platform}\0{author_id}".encode(), "sha256")
    return "anon-" + digest.hexdigest()


@dataclass(frozen=True)
class SourcePage:
    posts: tuple[SourcePost, ...]
    next_cursor: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(Protocol):
    name: str
    min_interval_seconds: int

    def fetch_page(self, cursor: dict[str, Any] | None, limit: int) -> SourcePage: ...


TRANSPORT = (
    "港鐵", "港铁", "mtr", "東鐵", "东铁", "east rail", "香港", "hong kong",
    "大圍", "大围", "九龍塘", "九龙塘", "旺角東", "旺角东", "紅磡", "红磡",
    "會展", "会展", "金鐘", "金钟", "tai wai", "kowloon tong", "mong kok east",
    "hung hom", "exhibition centre", "admiralty",
)
DISRUPTION = (
    "延誤", "延误", "停運", "停运", "暫停", "暂停", "故障", "擠迫", "挤迫",
    "擁擠", "拥挤", "關閉", "关闭", "封站", "恢復", "恢复", "受阻", "中斷", "中断",
    "delay", "suspend", "disruption", "failure", "fault", "crowd", "closed", "closure",
    "resum", "restored", "interrupted",
)
NEGATED = re.compile(
    r"(?:沒有|没有|並無|并无|無|无)\s*(?:延誤|延误|故障|停運|停运|中斷|中断)|"
    r"\bno\s+(?:delays?|disruptions?|faults?|closures?)\b", re.I,
)


def filter_reason(post: SourcePost, since: datetime, now: datetime,
                  extra_keywords: tuple[str, ...] = ()) -> str | None:
    """Conservative relevance filter, not a fact checker or event classifier."""
    if not post.text.strip():
        return "empty_text"
    if post.published_at is None:
        return "missing_publication_time"
    if post.published_at < since:
        return "outside_window"
    if post.published_at > now:
        return "future_publication_time"
    text = post.text.casefold()
    if post.provenance == "real" and any(x in text for x in ("【模拟", "【模擬", "[test data]")):
        return "test_marker"
    without_negation = NEGATED.sub("", text)
    if not any(x in text for x in TRANSPORT):
        return "unrelated_transport"
    if not any(x in without_negation for x in (*DISRUPTION, *extra_keywords)):
        return "unrelated_topic"
    return None
