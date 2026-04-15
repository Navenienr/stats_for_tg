from __future__ import annotations

from typing import Iterable, Sequence

from models.schemas import ChannelStatsResult, PostStats


def _truncate(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width <= 3:
        return "." * width
    return f"{value[: width - 3]}..."


def _render_ascii_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    right_aligned_columns: set[int] | None = None,
) -> str:
    aligned = right_aligned_columns or set()
    prepared_rows = [list(row) for row in rows]
    widths = [len(header) for header in headers]
    for row in prepared_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def _format_row(cells: Sequence[str]) -> str:
        formatted = []
        for idx, cell in enumerate(cells):
            if idx in aligned:
                formatted.append(f" {cell.rjust(widths[idx])} ")
            else:
                formatted.append(f" {cell.ljust(widths[idx])} ")
        return "|" + "|".join(formatted) + "|"

    lines = [border, _format_row(headers), border]
    for row in prepared_rows:
        lines.append(_format_row(row))
    lines.append(border)
    return "\n".join(lines)


def _format_channel_overview(results: list[ChannelStatsResult]) -> str:
    headers = [
        "Channel",
        "Username",
        "Subscribers",
        "Posts",
        "Views sum",
        "Reposts sum",
        "Comments sum",
        "Reactions sum",
        "Avg views",
        "Avg ER %",
        "Unavailable",
    ]
    rows: list[list[str]] = []

    for channel in results:
        posts = channel.post_metrics
        views = [post.views for post in posts if post.views is not None]
        ers = [post.engagement_rate for post in posts if post.engagement_rate is not None]
        total_views = sum(views)
        total_forwards = sum(post.forwards or 0 for post in posts)
        total_replies = sum(post.replies for post in posts)
        total_reactions = sum(post.reactions_total for post in posts)
        avg_views = f"{sum(views) / len(views):.1f}" if views else "n/a"
        avg_er = f"{sum(ers) / len(ers):.2f}" if ers else "n/a"
        rows.append(
            [
                _truncate(channel.channel_title, 30),
                channel.username or "-",
                str(channel.participants_count) if channel.participants_count is not None else "n/a",
                str(len(posts)),
                str(total_views),
                str(total_forwards),
                str(total_replies),
                str(total_reactions),
                avg_views,
                avg_er,
                str(len(channel.unavailable_metrics)),
            ]
        )

    return _render_ascii_table(headers, rows, right_aligned_columns={2, 3, 4, 5, 6, 7, 8, 9, 10})


def _flatten_posts(results: list[ChannelStatsResult]) -> list[tuple[ChannelStatsResult, PostStats]]:
    pairs: list[tuple[ChannelStatsResult, PostStats]] = []
    for channel in results:
        for post in channel.post_metrics:
            pairs.append((channel, post))
    return pairs


def _format_top_posts(results: list[ChannelStatsResult], limit: int) -> str:
    headers = ["Date", "Channel", "Message ID", "Views", "ER %", "Preview"]
    pairs = _flatten_posts(results)
    pairs.sort(key=lambda item: item[1].views or 0, reverse=True)

    rows: list[list[str]] = []
    for channel, post in pairs[: max(limit, 0)]:
        er = "n/a" if post.engagement_rate is None else f"{post.engagement_rate:.2f}"
        rows.append(
            [
                post.date.date().isoformat(),
                _truncate(channel.channel_title, 20),
                str(post.message_id),
                str(post.views) if post.views is not None else "n/a",
                er,
                _truncate(post.text_preview.replace("\n", " "), 42),
            ]
        )

    if not rows:
        rows.append(["-", "-", "-", "-", "-", "No posts in selected period"])

    return _render_ascii_table(headers, rows, right_aligned_columns={2, 3, 4})


def build_ascii_report(results: list[ChannelStatsResult], top_posts_limit: int = 10) -> str:
    channels_count = len(results)
    posts_count = sum(len(channel.post_metrics) for channel in results)
    views_sum = sum(post.views or 0 for channel in results for post in channel.post_metrics)
    forwards_sum = sum(post.forwards or 0 for channel in results for post in channel.post_metrics)
    replies_sum = sum(post.replies for channel in results for post in channel.post_metrics)
    reactions_sum = sum(post.reactions_total for channel in results for post in channel.post_metrics)
    lines = [
        "",
        "Telegram statistics report (ASCII)",
        f"Channels: {channels_count} | Posts: {posts_count}",
        (
            "Totals in selected period: "
            f"views={views_sum}, reposts={forwards_sum}, comments={replies_sum}, reactions={reactions_sum}"
        ),
        "",
        "Channel overview",
        _format_channel_overview(results),
        "",
        f"Top posts by views (top {max(top_posts_limit, 0)})",
        _format_top_posts(results, top_posts_limit),
        "",
    ]
    return "\n".join(lines)
