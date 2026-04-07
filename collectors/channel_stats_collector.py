from __future__ import annotations

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel

from models.schemas import ChannelStatsResult, UnavailableMetric
from telegram.client import call_with_floodwait_retry


async def collect_channel_base_stats(
    client: TelegramClient,
    channel: Channel,
) -> ChannelStatsResult:
    unavailable: list[UnavailableMetric] = []
    participants_count = channel.participants_count
    about = None
    can_view_stats = False

    try:
        full_channel = await call_with_floodwait_retry(
            lambda: client(GetFullChannelRequest(channel))
        )
        full_chat = full_channel.full_chat
        participants_count = getattr(full_chat, "participants_count", participants_count)
        about = getattr(full_chat, "about", None)
        can_view_stats = bool(getattr(full_chat, "can_view_stats", False))
    except RPCError as exc:
        unavailable.append(
            UnavailableMetric(
                metric="channel_full_info",
                reason="no_access",
                details=str(exc),
            )
        )

    return ChannelStatsResult(
        channel_id=channel.id,
        channel_title=channel.title or str(channel.id),
        username=channel.username,
        is_megagroup=bool(channel.megagroup),
        participants_count=participants_count,
        about=about,
        can_view_stats=can_view_stats,
        base_metrics={
            "broadcast": bool(channel.broadcast),
            "megagroup": bool(channel.megagroup),
            "verified": bool(channel.verified),
            "restricted": bool(channel.restricted),
            "participants_count": participants_count,
        },
        unavailable_metrics=unavailable,
    )
