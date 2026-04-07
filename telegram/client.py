from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telethon import TelegramClient
from telethon.errors import FloodWaitError

from config import Config

LOG = logging.getLogger(__name__)
T = TypeVar("T")


def create_client(config: Config) -> TelegramClient:
    return TelegramClient(config.session_name, config.api_id, config.api_hash)


async def call_with_floodwait_retry(
    request_call: Callable[[], Awaitable[T]],
    retries: int = 3,
) -> T:
    attempt = 0
    while True:
        try:
            return await request_call()
        except FloodWaitError as exc:
            attempt += 1
            if attempt > retries:
                raise
            wait_for = exc.seconds + 1
            LOG.warning("FloodWait hit, sleeping for %s seconds", wait_for)
            await asyncio.sleep(wait_for)
