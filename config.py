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
SCOPE_HISTORY_FILE = Path("collection_scope_history.json")
SCOPE_HISTORY_LIMIT = 10
CHANNEL_RE = re.compile(r"^@?[A-Za-z0-9_]{5,}$")
API_ID_MAX = 2_147_483_647


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
        if api_id <= 0 or api_id > API_ID_MAX:
            raise ValueError(f"api_id must be in range 1..{API_ID_MAX}.")

        post_limit = int(payload.get("post_limit", 0))
        if post_limit < 0:
            raise ValueError("post_limit must be zero or a positive integer.")

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


def _prompt_api_id(current: Optional[str]) -> str:
    while True:
        value = _prompt_value("Telegram API_ID", current, required=True)
        try:
            parsed = int(value)
        except ValueError:
            print("API_ID must be an integer.")
            current = None
            continue
        if parsed <= 0 or parsed > API_ID_MAX:
            print(f"API_ID must be in range 1..{API_ID_MAX}.")
            current = None
            continue
        return str(parsed)


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
        "post_limit": os.getenv("POST_LIMIT", "0").strip(),
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

    api_id = _prompt_api_id(_normalize_optional(initial.get("api_id")))
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
        _normalize_optional(initial.get("post_limit")) or "0",
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
        try:
            return Config.from_dict(merged)
        except ValueError as exc:
            print(
                "Saved settings are invalid and need reconfiguration: "
                f"{exc}"
            )
            reconfigure = True

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


def _read_scope_history() -> list[dict[str, str]]:
    if not SCOPE_HISTORY_FILE.exists():
        return []

    try:
        raw = json.loads(SCOPE_HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if isinstance(raw, dict):
        entries = raw.get("recent_scopes", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        entries = []

    history: list[dict[str, str]] = []
    if not isinstance(entries, list):
        return history

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        channel_username = str(entry.get("channel_username", "")).strip()
        date_from = str(entry.get("date_from", "")).strip()
        date_to = str(entry.get("date_to", "")).strip()
        if not channel_username or not date_from or not date_to:
            continue
        history.append(
            {
                "channel_username": channel_username,
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        if len(history) >= SCOPE_HISTORY_LIMIT:
            break
    return history


def _write_scope_history(history: list[dict[str, str]]) -> None:
    payload = {"recent_scopes": history[:SCOPE_HISTORY_LIMIT]}
    SCOPE_HISTORY_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _remember_scope(history: list[dict[str, str]], scope: dict[str, str]) -> None:
    deduplicated = [entry for entry in history if entry != scope]
    updated = [scope, *deduplicated][:SCOPE_HISTORY_LIMIT]
    _write_scope_history(updated)


def _prompt_scope_choice(
    history: list[dict[str, str]],
) -> tuple[Optional[dict[str, str]], Optional[str]]:
    if not history:
        return None, None

    print("Recent collection scopes:")
    for idx, scope in enumerate(history, start=1):
        print(
            f"{idx}. {scope['channel_username']} | "
            f"{scope['date_from']}..{scope['date_to']}"
        )
    print("")

    while True:
        value = input(
            "Choose scope number, or type @channel for new scope [Enter for manual input]: "
        ).strip()
        if not value:
            return None, None

        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(history):
                return history[index - 1], None
            print("Number is out of range.")
            continue

        try:
            normalized = Config.normalize_channel_username(value)
            return None, normalized
        except ValueError:
            print("Enter a list number or a valid @channel username.")


def _prompt_period(current_date_from: str, current_date_to: str) -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    while True:
        print("\nSelect period:")
        print(f"1. Keep current ({current_date_from}..{current_date_to})")
        print(f"2. Today ({today.isoformat()})")
        print(f"3. Last 7 days ({(today - timedelta(days=6)).isoformat()}..{today.isoformat()})")
        print(f"4. Last 30 days ({(today - timedelta(days=29)).isoformat()}..{today.isoformat()})")
        print("5. Custom dates")
        choice = input("Choose period [1-5, default 1]: ").strip()
        if not choice:
            choice = "1"

        if choice == "1":
            return current_date_from, current_date_to
        if choice == "2":
            value = today.isoformat()
            return value, value
        if choice == "3":
            return (today - timedelta(days=6)).isoformat(), today.isoformat()
        if choice == "4":
            return (today - timedelta(days=29)).isoformat(), today.isoformat()
        if choice == "5":
            date_from = _prompt_value(
                "Date from (YYYY-MM-DD)",
                current_date_from,
                required=True,
            )
            date_to = _prompt_value(
                "Date to (YYYY-MM-DD)",
                current_date_to,
                required=True,
            )
            return date_from, date_to
        print("Please enter a number from 1 to 5.")


def prompt_collection_scope(config: Config) -> Config:
    print("\nConfigure collection scope for this run.")
    print("Press Enter to keep the value shown in brackets.\n")
    history = _read_scope_history()

    chosen_scope, manual_channel_override = _prompt_scope_choice(history)
    if chosen_scope is not None:
        payload = config.to_dict()
        payload["channel_username"] = chosen_scope["channel_username"]
        payload["date_from"] = chosen_scope["date_from"]
        payload["date_to"] = chosen_scope["date_to"]
        try:
            selected = Config.from_dict(payload)
            _remember_scope(history, chosen_scope)
            return selected
        except ValueError:
            print("Saved scope is invalid, please enter values manually.\n")

    current_channel = manual_channel_override or config.channel_username
    current_date_from = config.date_from
    current_date_to = config.date_to

    while True:
        channel_username = _prompt_value(
            "Target channel username (@channel)",
            current_channel,
            required=True,
        )
        date_from, date_to = _prompt_period(current_date_from, current_date_to)

        payload = config.to_dict()
        payload["channel_username"] = channel_username
        payload["date_from"] = date_from
        payload["date_to"] = date_to

        try:
            selected = Config.from_dict(payload)
            _remember_scope(
                history,
                {
                    "channel_username": selected.channel_username,
                    "date_from": selected.date_from,
                    "date_to": selected.date_to,
                },
            )
            return selected
        except ValueError as exc:
            print(f"Invalid collection scope: {exc}")
            print("Please try again.\n")
            current_channel = channel_username
            current_date_from = date_from
            current_date_to = date_to
