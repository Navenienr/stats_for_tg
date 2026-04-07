from __future__ import annotations

from pathlib import Path

from models.schemas import ChannelStatsResult


def build_summary(results: list[ChannelStatsResult]) -> str:
    total_channels = len(results)
    total_posts = sum(len(item.post_metrics) for item in results)
    with_advanced = sum(1 for item in results if item.advanced_metrics is not None)

    lines = [
        "Telegram channel stats summary",
        "=" * 32,
        f"Channels processed: {total_channels}",
        f"Posts processed: {total_posts}",
        f"Channels with advanced stats: {with_advanced}",
        "",
    ]

    for channel in results:
        avg_views = None
        if channel.post_metrics:
            values = [post.views for post in channel.post_metrics if post.views is not None]
            if values:
                avg_views = round(sum(values) / len(values), 2)
        lines.extend(
            [
                f"- {channel.channel_title} ({channel.channel_id})",
                f"  posts: {len(channel.post_metrics)}",
                f"  participants: {channel.participants_count}",
                f"  avg_views: {avg_views if avg_views is not None else 'n/a'}",
                f"  unavailable_metrics: {len(channel.unavailable_metrics)}",
            ]
        )
    return "\n".join(lines)


def write_summary(results: list[ChannelStatsResult], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "summary.txt"
    target.write_text(build_summary(results), encoding="utf-8")
    return target
