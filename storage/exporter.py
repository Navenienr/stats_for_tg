from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from models.schemas import ChannelStatsResult


def _ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def export_json(
    results: list[ChannelStatsResult],
    output_dir: Path,
    run_parameters: dict[str, object],
) -> Path:
    target = _ensure_output_dir(output_dir) / "channels_stats.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_parameters": run_parameters,
        "results": [item.to_dict() for item in results],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def export_channels_csv(results: list[ChannelStatsResult], output_dir: Path) -> Path:
    target = _ensure_output_dir(output_dir) / "channels_overview.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "channel_id",
                "channel_title",
                "username",
                "is_megagroup",
                "participants_count",
                "can_view_stats",
            ],
        )
        writer.writeheader()
        for channel in results:
            writer.writerow(
                {
                    "channel_id": channel.channel_id,
                    "channel_title": channel.channel_title,
                    "username": channel.username or "",
                    "is_megagroup": channel.is_megagroup,
                    "participants_count": channel.participants_count,
                    "can_view_stats": channel.can_view_stats,
                }
            )
    return target


def export_posts_csv(results: list[ChannelStatsResult], output_dir: Path) -> Path:
    target = _ensure_output_dir(output_dir) / "posts_metrics.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "channel_id",
                "message_id",
                "date",
                "text_preview",
                "views",
                "forwards",
                "replies",
                "reactions_total",
                "engagement_rate",
            ],
        )
        writer.writeheader()
        for channel in results:
            for post in channel.post_metrics:
                writer.writerow(
                    {
                        "channel_id": post.channel_id,
                        "message_id": post.message_id,
                        "date": post.date.isoformat(),
                        "text_preview": post.text_preview,
                        "views": post.views,
                        "forwards": post.forwards,
                        "replies": post.replies,
                        "reactions_total": post.reactions_total,
                        "engagement_rate": post.engagement_rate,
                    }
                )
    return target


def export_unavailable_metrics_csv(
    results: list[ChannelStatsResult],
    output_dir: Path,
) -> Path:
    target = _ensure_output_dir(output_dir) / "unavailable_metrics.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["channel_id", "channel_title", "metric", "reason", "details"],
        )
        writer.writeheader()
        for channel in results:
            for unavailable in channel.unavailable_metrics:
                writer.writerow(
                    {
                        "channel_id": channel.channel_id,
                        "channel_title": channel.channel_title,
                        "metric": unavailable.metric,
                        "reason": unavailable.reason,
                        "details": unavailable.details or "",
                    }
                )
    return target


def export_all(
    results: list[ChannelStatsResult],
    output_dir: Path,
    run_parameters: dict[str, object],
) -> dict[str, Path]:
    return {
        "json": export_json(results, output_dir, run_parameters),
        "channels_csv": export_channels_csv(results, output_dir),
        "posts_csv": export_posts_csv(results, output_dir),
        "unavailable_csv": export_unavailable_metrics_csv(results, output_dir),
    }


def export_base_stats(
    results: list[ChannelStatsResult],
    base_stats_file: Path,
    run_parameters: dict[str, object],
) -> Path:
    run_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_parameters": run_parameters,
        "channels_count": len(results),
        "results": [item.to_dict() for item in results],
    }

    history: dict[str, object] = {"runs": []}
    if base_stats_file.exists():
        try:
            history = json.loads(base_stats_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = {"runs": []}

    runs = history.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(run_payload)
    history["runs"] = runs

    base_stats_file.parent.mkdir(parents=True, exist_ok=True)
    base_stats_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return base_stats_file
