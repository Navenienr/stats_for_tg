from __future__ import annotations

import logging

from telethon import TelegramClient
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError

from config import Config

LOG = logging.getLogger(__name__)


async def ensure_authorized(client: TelegramClient, config: Config) -> None:
    await client.connect()

    if await client.is_user_authorized():
        LOG.info("Telegram session is already authorized.")
        return

    LOG.info("Starting interactive Telegram authorization...")
    await client.send_code_request(config.phone_number)
    code = input("Enter Telegram login code: ").strip()

    try:
        await client.sign_in(phone=config.phone_number, code=code)
    except SessionPasswordNeededError:
        password = input("Enter Telegram 2FA password: ").strip()
        await client.sign_in(password=password)
    except PhoneCodeInvalidError as exc:
        raise RuntimeError("Telegram login code is invalid.") from exc

    LOG.info("Authorization successful. Session saved locally.")
