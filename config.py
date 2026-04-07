from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

SETTINGS_FILE = Path("user_settings.json")
CHANNEL_RE = re.compile(r"^@?[A-Za-z0-9_]{5,}$")


@dataclass(slots=True)
class Config:
    api_id: int
    api_hash: str
    phone_number: str
    session_name: str
    output_dir: Path
    post_limit: int
    channel_username: str
    date_from: str
    date_to: str
    log_level: str
    base_stats_file: Path

    @staticmethod
    def normalize_channel_username(raw: str) -> str:
        username = raw.strip()
        if not username:
            raise ValueError("channel_username is required.")
        if not CHANNEL_RE.match(username):
            raise ValueError("channel_username must look like @channel_name.")
        if not username.startswith("@"):
            username = f"@{username}"
        return username

    @staticmethod
    def parse_date_str(raw: str, field_name: str) -> date:
        try:
            return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc

    def utc_window(self) -> tuple[datetime, datetime]:
        start_date = self.parse_date_str(self.date_from, "date_from")
        end_date = self.parse_date_str(self.date_to, "date_to")
        if start_date > end_date:
            raise ValueError("date_from must be less than or equal to date_to.")

        start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
        return start_dt, end_dt

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Config":
        api_id_raw = str(payload.get("api_id", "")).strip()
        api_hash = str(payload.get("api_hash", "")).strip()
        phone_number = str(payload.get("phone_number", "")).strip()
        if not api_id_raw or not api_hash or not phone_number:
            raise ValueError("api_id, api_hash and phone_number are required.")

        try:
            api_id = int(api_id_raw)
        except ValueError as exc:
            raise ValueError("api_id must be an integer.") from exc

        post_limit = int(payload.get("post_limit", 200))
        if post_limit <= 0:
            raise ValueError("post_limit must be a positive integer.")

        raw_channel = str(
            payload.get("channel_username")
            or payload.get("channel_filter")
            or ""
        ).strip()
        channel_username = cls.normalize_channel_username(raw_channel)

        date_from = str(payload.get("date_from", "")).strip()
        date_to = str(payload.get("date_to", "")).strip()
        if not date_from or not date_to:
            # Backward compatibility for older settings that used days_back.
            days_back_raw = payload.get("days_back")
            if days_back_raw not in (None, ""):
                days_back = int(days_back_raw)
                if days_back <= 0:
                    raise ValueError("days_back must be a positive integer.")
                end_date = datetime.now(timezone.utc).date()
                start_date = end_date - timedelta(days=days_back)
                date_from = start_date.isoformat()
                date_to = end_date.isoformat()

        if not date_from or not date_to:
            raise ValueError("date_from and date_to are required.")

        start_date = cls.parse_date_str(date_from, "date_from")
        end_date = cls.parse_date_str(date_to, "date_to")
        if start_date > end_date:
            raise ValueError("date_from must be less than or equal to date_to.")

        output_dir = Path(str(payload.get("output_dir", "exports")).strip() or "exports")
        base_stats_file = Path(
            str(payload.get("base_stats_file", "stats_base.json")).strip() or "stats_base.json"
        )

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone_number,
            session_name=(str(payload.get("session_name", "tg_stats_session")).strip() or "tg_stats_session"),
            output_dir=output_dir,
            post_limit=post_limit,
            channel_username=channel_username,
            date_from=date_from,
            date_to=date_to,
            log_level=str(payload.get("log_level", "INFO")).upper(),
            base_stats_file=base_stats_file,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_id": self.api_id,
            "api_hash": self.api_hash,
            "phone_number": self.phone_number,
            "session_name": self.session_name,
            "output_dir": str(self.output_dir),
            "post_limit": self.post_limit,
            "channel_username": self.channel_username,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "log_level": self.log_level,
            "base_stats_file": str(self.base_stats_file),
        }


def _prompt_value(prompt: str, current: Optional[str] = None, required: bool = False) -> str:
    while True:
        suffix = f" [{current}]" if current else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if current is not None:
            return current
        if not required:
            return ""
        print("Value is required.")


def _normalize_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _build_default_payload_from_env() -> dict[str, Any]:
    load_dotenv()
    return {
        "api_id": os.getenv("API_ID", "").strip(),
        "api_hash": os.getenv("API_HASH", "").strip(),
        "phone_number": os.getenv("PHONE_NUMBER", "").strip(),
        "session_name": os.getenv("SESSION_NAME", "tg_stats_session").strip(),
        "output_dir": os.getenv("OUTPUT_DIR", "exports").strip(),
        "post_limit": os.getenv("POST_LIMIT", "200").strip(),
        "channel_username": os.getenv("CHANNEL_USERNAME", "").strip() or os.getenv("CHANNEL_FILTER", "").strip(),
        "date_from": os.getenv("DATE_FROM", "").strip(),
        "date_to": os.getenv("DATE_TO", "").strip(),
        "days_back": os.getenv("DAYS_BACK", "").strip(),
        "log_level": os.getenv("LOG_LEVEL", "INFO").strip(),
        "base_stats_file": os.getenv("BASE_STATS_FILE", "stats_base.json").strip(),
    }


def _interactive_setup(initial: dict[str, Any]) -> dict[str, Any]:
    print("\nFirst-time setup. Enter Telegram and default collector settings.")
    print("Press Enter to keep the value shown in brackets.\n")

    api_id = _prompt_value("Telegram API_ID", _normalize_optional(initial.get("api_id")), required=True)
    api_hash = _prompt_value(
        "Telegram API_HASH",
        _normalize_optional(initial.get("api_hash")),
        required=True,
    )
    phone_number = _prompt_value(
        "Telegram PHONE_NUMBER",
        _normalize_optional(initial.get("phone_number")),
        required=True,
    )
    session_name = _prompt_value(
        "Session name",
        _normalize_optional(initial.get("session_name")) or "tg_stats_session",
    )
    output_dir = _prompt_value(
        "Output directory",
        _normalize_optional(initial.get("output_dir")) or "exports",
    )
    post_limit = _prompt_value(
        "Default post limit",
        _normalize_optional(initial.get("post_limit")) or "200",
    )
    channel_username = _prompt_value(
        "Target channel username (@channel)",
        _normalize_optional(initial.get("channel_username")) or "",
        required=True,
    )
    date_from = _prompt_value(
        "Date from (YYYY-MM-DD)",
        _normalize_optional(initial.get("date_from")) or "",
        required=True,
    )
    date_to = _prompt_value(
        "Date to (YYYY-MM-DD)",
        _normalize_optional(initial.get("date_to")) or "",
        required=True,
    )
    log_level = _prompt_value("Log level", _normalize_optional(initial.get("log_level")) or "INFO")
    base_stats_file = _prompt_value(
        "Base stats file path",
        _normalize_optional(initial.get("base_stats_file")) or "stats_base.json",
    )

    return {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone_number": phone_number,
        "session_name": session_name,
        "output_dir": output_dir,
        "post_limit": post_limit,
        "channel_username": channel_username,
        "date_from": date_from,
        "date_to": date_to,
        "log_level": log_level,
        "base_stats_file": base_stats_file,
    }


def _read_settings_file(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(reconfigure: bool = False) -> Config:
    defaults = _build_default_payload_from_env()
    settings_payload = _read_settings_file(SETTINGS_FILE)
    if settings_payload and not reconfigure:
        merged = {**defaults, **settings_payload}
        return Config.from_dict(merged)

    initial = {**defaults}
    if settings_payload:
        initial.update(settings_payload)
    payload = _interactive_setup(initial)
    config = Config.from_dict(payload)

    SETTINGS_FILE.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def save_config(config: Config) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
