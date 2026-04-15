from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from auth.session_manager import ensure_authorized
from collectors.advanced_stats_collector import collect_advanced_stats
from collectors.channel_stats_collector import collect_channel_base_stats
from collectors.post_stats_collector import collect_post_metrics
from config import Config, load_config, prompt_collection_scope, save_config
from models.schemas import ChannelStatsResult, UnavailableMetric
from reports.ascii_table_report import build_ascii_report
from reports.summary_report import write_summary
from storage.exporter import export_all, export_base_stats
from telegram.channel_discovery import resolve_channel_by_username
from telegram.client import create_client


def _prompt_main_action() -> str:
    while True:
        print("\nWhat do you want to do?")
        print("1. Collect channel statistics")
        print("2. Reconfigure saved Telegram settings")
        print("3. Exit")
        value = input("Choose action [1-3, default 1]: ").strip()
        if not value:
            return "1"
        if value in {"1", "2", "3"}:
            return value
        print("Please enter 1, 2 or 3.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Telegram channel statistics.")
    parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="Run interactive setup again and rewrite saved settings.",
    )
    parser.add_argument(
        "--save-settings",
        action="store_true",
        help="Save CLI overrides into user_settings.json for future runs.",
    )
    parser.add_argument(
        "--post-limit",
        type=int,
        help="Max posts per channel (0 = all posts in date range).",
    )
    parser.add_argument("--channel", type=str, help="Target channel username, e.g. @example.")
    parser.add_argument("--date-from", type=str, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--date-to", type=str, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--output-dir", type=str, help="Directory for exports.")
    parser.add_argument(
        "--no-ascii-table",
        action="store_true",
        help="Disable ASCII table report in terminal output.",
    )
    parser.add_argument(
        "--ascii-top-posts",
        type=int,
        default=10,
        help="How many posts to show in ASCII top table (default: 10).",
    )
    parser.add_argument(
        "--base-stats-file",
        type=str,
        help="Path to persistent base stats JSON file.",
    )
    parser.add_argument(
        "--no-menu",
        action="store_true",
        help="Disable beginner menu and run directly.",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    if not args.no_menu:
        action = _prompt_main_action()
        if action == "2":
            args.reconfigure = True
        elif action == "3":
            print("Bye.")
            return

    config = load_config(reconfigure=args.reconfigure)

    if args.post_limit is not None:
        if args.post_limit < 0:
            raise ValueError("--post-limit must be greater than or equal to 0.")
        config.post_limit = args.post_limit
    else:
        # By default collect all posts inside selected period.
        config.post_limit = 0
    if args.channel:
        config.channel_username = args.channel
    if args.date_from:
        config.date_from = args.date_from
    if args.date_to:
        config.date_to = args.date_to
    if args.output_dir:
        config.output_dir = Path(args.output_dir)
    if args.base_stats_file:
        config.base_stats_file = Path(args.base_stats_file)
    if args.ascii_top_posts < 0:
        raise ValueError("--ascii-top-posts must be greater than or equal to 0.")
    config = Config.from_dict(config.to_dict())
    config = prompt_collection_scope(config)

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log = logging.getLogger("main")

    client = create_client(config)
    results: list[ChannelStatsResult] = []
    date_from_utc, date_to_utc = config.utc_window()

    try:
        await ensure_authorized(client, config)
        channel = await resolve_channel_by_username(client, config.channel_username)
        log.info("Collecting %s in range %s..%s", config.channel_username, config.date_from, config.date_to)

        channel_result = await collect_channel_base_stats(client, channel)
        channel_result.post_metrics = await collect_post_metrics(
            client=client,
            channel=channel,
            post_limit=config.post_limit,
            date_from_utc=date_from_utc,
            date_to_utc=date_to_utc,
            participants_count=channel_result.participants_count,
        )

        if channel_result.can_view_stats:
            advanced_metrics, unavailable = await collect_advanced_stats(client, channel)
            channel_result.advanced_metrics = advanced_metrics
            channel_result.unavailable_metrics.extend(unavailable)
        else:
            channel_result.unavailable_metrics.append(
                UnavailableMetric(
                    metric="advanced_stats",
                    reason="no_access",
                    details="Telegram reports that channel stats are unavailable.",
                )
            )
        results.append(channel_result)
    finally:
        await client.disconnect()

    run_parameters = {
        "post_limit": config.post_limit,
        "channel_username": config.channel_username,
        "date_from": config.date_from,
        "date_to": config.date_to,
        "output_dir": str(config.output_dir),
    }

    paths = export_all(results, config.output_dir, run_parameters)
    base_path = export_base_stats(
        results=results,
        base_stats_file=config.base_stats_file,
        run_parameters=run_parameters,
    )
    summary_path = write_summary(results, config.output_dir)

    log.info("Export completed:")
    for name, path in paths.items():
        log.info("- %s: %s", name, path)
    log.info("- summary: %s", summary_path)
    log.info("- base_stats: %s", base_path)

    if not args.no_ascii_table:
        print(build_ascii_report(results, top_posts_limit=args.ascii_top_posts))

    if args.save_settings:
        save_config(config)
        log.info("Updated user settings were saved.")


if __name__ == "__main__":
    asyncio.run(run())
