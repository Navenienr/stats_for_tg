from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Channel, Message

from models.schemas import PostStats


def _extract_reactions(message: Message) -> tuple[int, dict[str, int]]:
    reactions_total = 0
    breakdown: dict[str, int] = {}

    reactions = getattr(message, "reactions", None)
    if not reactions or not getattr(reactions, "results", None):
        return reactions_total, breakdown

    for item in reactions.results:
        count = int(getattr(item, "count", 0))
        reaction_value = getattr(item, "reaction", None)
        key = str(reaction_value)
        reactions_total += count
        breakdown[key] = breakdown.get(key, 0) + count

    return reactions_total, breakdown


def _build_preview(text: str, max_len: int = 90) -> str:
    short = " ".join(text.split())
    if len(short) <= max_len:
        return short
    return short[: max_len - 3] + "..."


async def collect_post_metrics(
    client: TelegramClient,
    channel: Channel,
    post_limit: int,
    date_from_utc: datetime,
    date_to_utc: datetime,
    participants_count: Optional[int],
) -> list[PostStats]:
    posts: list[PostStats] = []
    # offset_date is exclusive upper bound, so pass one second after the range end.
    offset_date = date_to_utc + timedelta(seconds=1)

    async for message in client.iter_messages(
        entity=channel,
        limit=post_limit,
        offset_date=offset_date,
    ):
        if not message or not message.id:
            continue

        message_date = message.date
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)
        if message_date < date_from_utc:
            break
        if message_date > date_to_utc:
            continue

        text_preview = _build_preview(message.message or "")
        views = int(message.views) if message.views is not None else None
        forwards = int(message.forwards) if message.forwards is not None else None
        replies = int(getattr(getattr(message, "replies", None), "replies", 0) or 0)
        reactions_total, reactions_breakdown = _extract_reactions(message)

        interactions = reactions_total + replies + (forwards or 0)
        engagement_rate = None
        if participants_count and participants_count > 0:
            engagement_rate = round(interactions / participants_count, 6)

        posts.append(
            PostStats(
                channel_id=channel.id,
                message_id=message.id,
                date=message_date,
                text_preview=text_preview,
                views=views,
                forwards=forwards,
                replies=replies,
                reactions_total=reactions_total,
                reactions_breakdown=reactions_breakdown,
                engagement_rate=engagement_rate,
            )
        )

    return posts
