from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(slots=True)
class UnavailableMetric:
    metric: str
    reason: str
    details: Optional[str] = None


@dataclass(slots=True)
class PostStats:
    channel_id: int
    message_id: int
    date: datetime
    text_preview: str
    views: Optional[int]
    forwards: Optional[int]
    replies: int
    reactions_total: int
    reactions_breakdown: dict[str, int]
    engagement_rate: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["date"] = self.date.isoformat()
        return payload


@dataclass(slots=True)
class ChannelStatsResult:
    channel_id: int
    channel_title: str
    username: Optional[str]
    is_megagroup: bool
    participants_count: Optional[int]
    about: Optional[str]
    can_view_stats: bool
    base_metrics: dict[str, Any]
    post_metrics: list[PostStats] = field(default_factory=list)
    advanced_metrics: Optional[dict[str, Any]] = None
    unavailable_metrics: list[UnavailableMetric] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["post_metrics"] = [post.to_dict() for post in self.post_metrics]
        return payload
