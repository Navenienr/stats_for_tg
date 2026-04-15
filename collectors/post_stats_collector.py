from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Channel, Message

from models.schemas import PostStats


@dataclass(slots=True)
class _PostAccumulator:
    channel_id: int
    message_id: int
    date: datetime
    text_preview: str
    views: Optional[int]
    forwards: Optional[int]
    comments: int
    reactions_total: int
    reactions_breakdown: dict[str, int]
    representative_score: tuple[int, int, int, int]


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


def _extract_comments(message: Message) -> int:
    replies_obj = getattr(message, "replies", None)
    if not replies_obj:
        return 0

    # In channel posts comments are represented via linked discussion thread.
    # If Telegram explicitly marks that no comments thread is present, treat as 0.
    has_comments_thread = getattr(replies_obj, "comments", None)
    if has_comments_thread is False and bool(getattr(message, "post", False)):
        return 0
    return int(getattr(replies_obj, "replies", 0) or 0)


def _should_group_as_single_post(message: Message) -> bool:
    # Photo albums should be treated as one publication.
    # Video messages are counted as separate posts.
    return bool(getattr(message, "photo", None))


def _representative_score(
    text_preview: str,
    views: Optional[int],
    forwards: Optional[int],
    comments: int,
    reactions_total: int,
    message_id: int,
) -> tuple[int, int, int, int]:
    has_text = 1 if text_preview else 0
    interactions = (forwards or 0) + comments + reactions_total
    return (has_text, views or -1, interactions, message_id)


def _build_accumulator(channel_id: int, message: Message) -> _PostAccumulator:
    text_preview = _build_preview(message.message or "")
    views = int(message.views) if message.views is not None else None
    forwards = int(message.forwards) if message.forwards is not None else None
    comments = _extract_comments(message)
    reactions_total, reactions_breakdown = _extract_reactions(message)
    score = _representative_score(
        text_preview=text_preview,
        views=views,
        forwards=forwards,
        comments=comments,
        reactions_total=reactions_total,
        message_id=int(message.id),
    )
    message_date = message.date
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    return _PostAccumulator(
        channel_id=channel_id,
        message_id=int(message.id),
        date=message_date,
        text_preview=text_preview,
        views=views,
        forwards=forwards,
        comments=comments,
        reactions_total=reactions_total,
        reactions_breakdown=reactions_breakdown,
        representative_score=score,
    )


def _merge_accumulator(current: _PostAccumulator, new: _PostAccumulator) -> _PostAccumulator:
    # For Telegram albums (grouped_id), counters can appear on different media items.
    # Use max values to avoid double-counting while preserving the strongest observed counter.
    if current.views is None:
        merged_views = new.views
    elif new.views is None:
        merged_views = current.views
    else:
        merged_views = max(current.views, new.views)

    if current.forwards is None:
        merged_forwards = new.forwards
    elif new.forwards is None:
        merged_forwards = current.forwards
    else:
        merged_forwards = max(current.forwards, new.forwards)

    merged_comments = max(current.comments, new.comments)
    merged_reactions_total = max(current.reactions_total, new.reactions_total)

    merged_breakdown = dict(current.reactions_breakdown)
    for reaction, count in new.reactions_breakdown.items():
        merged_breakdown[reaction] = max(merged_breakdown.get(reaction, 0), count)

    representative = current
    if new.representative_score > current.representative_score:
        representative = new

    return _PostAccumulator(
        channel_id=current.channel_id,
        message_id=representative.message_id,
        date=representative.date,
        text_preview=representative.text_preview,
        views=merged_views,
        forwards=merged_forwards,
        comments=merged_comments,
        reactions_total=merged_reactions_total,
        reactions_breakdown=merged_breakdown,
        representative_score=representative.representative_score,
    )


async def collect_post_metrics(
    client: TelegramClient,
    channel: Channel,
    post_limit: int,
    date_from_utc: datetime,
    date_to_utc: datetime,
    participants_count: Optional[int],
) -> list[PostStats]:
    grouped_posts: dict[int, _PostAccumulator] = {}
    standalone_posts: list[_PostAccumulator] = []
    # offset_date is exclusive upper bound, so pass one second after the range end.
    offset_date = date_to_utc + timedelta(seconds=1)

    async for message in client.iter_messages(
        entity=channel,
        limit=None,
        offset_date=offset_date,
    ):
        if not message or not message.id:
            continue
        if getattr(message, "action", None) is not None:
            continue

        message_date = message.date
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)
        if message_date < date_from_utc:
            break
        if message_date > date_to_utc:
            continue

        accumulator = _build_accumulator(channel.id, message)
        grouped_id = int(getattr(message, "grouped_id", 0) or 0)
        if grouped_id > 0 and _should_group_as_single_post(message):
            existing = grouped_posts.get(grouped_id)
            grouped_posts[grouped_id] = (
                accumulator if existing is None else _merge_accumulator(existing, accumulator)
            )
        else:
            standalone_posts.append(accumulator)

    all_accumulators = [*standalone_posts, *grouped_posts.values()]
    sorted_accumulators = sorted(
        all_accumulators,
        key=lambda item: (item.date, item.message_id),
        reverse=True,
    )
    if post_limit > 0:
        sorted_accumulators = sorted_accumulators[:post_limit]

    posts: list[PostStats] = []
    for item in sorted_accumulators:
        interactions = item.reactions_total + item.comments + (item.forwards or 0)
        engagement_rate = None
        if participants_count and participants_count > 0:
            engagement_rate = round(interactions / participants_count, 6)
        posts.append(
            PostStats(
                channel_id=item.channel_id,
                message_id=item.message_id,
                date=item.date,
                text_preview=item.text_preview,
                views=item.views,
                forwards=item.forwards,
                replies=item.comments,
                reactions_total=item.reactions_total,
                reactions_breakdown=item.reactions_breakdown,
                engagement_rate=engagement_rate,
            )
        )

    return posts
