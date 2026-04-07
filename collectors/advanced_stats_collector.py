from __future__ import annotations

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.stats import (
    GetBroadcastStatsRequest,
    GetMegagroupStatsRequest,
)
from telethon.tl.types import Channel

from models.schemas import UnavailableMetric
from telegram.client import call_with_floodwait_retry
from utils.serialization import serialize_value


async def collect_advanced_stats(
    client: TelegramClient,
    channel: Channel,
) -> tuple[dict | None, list[UnavailableMetric]]:
    unavailable: list[UnavailableMetric] = []

    try:
        if channel.megagroup:
            stats = await call_with_floodwait_retry(
                lambda: client(GetMegagroupStatsRequest(channel=channel, dark=False))
            )
        else:
            stats = await call_with_floodwait_retry(
                lambda: client(GetBroadcastStatsRequest(channel=channel, dark=False))
            )
        return serialize_value(stats), unavailable
    except RPCError as exc:
        unavailable.append(
            UnavailableMetric(
                metric="advanced_stats",
                reason="private_stats",
                details=str(exc),
            )
        )
        return None, unavailable
