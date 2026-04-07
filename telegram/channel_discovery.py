from __future__ import annotations

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import Channel


async def resolve_channel_by_username(
    client: TelegramClient,
    channel_username: str,
) -> Channel:
    try:
        entity = await client.get_entity(channel_username)
    except RPCError as exc:
        raise RuntimeError(
            f"Failed to resolve channel {channel_username}. Check username and access."
        ) from exc

    if not isinstance(entity, Channel):
        raise RuntimeError(f"{channel_username} is not a channel or supergroup.")

    return entity
