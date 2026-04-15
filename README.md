# Telegram Channel Statistics Collector

Python script that collects maximum available channel statistics via Telegram user session (`Telethon`) and exports results to JSON/CSV.
On first run, the script asks for required settings interactively and saves them into `user_settings.json`.

## Features

- User-session auth (`api_id` + `api_hash` + login code + optional 2FA password).
- First-run interactive setup with persistent settings in `user_settings.json`.
- Reconfigure saved defaults anytime via `--reconfigure`.
- Target collection for one channel via `--channel @username`.
- Date-range collection via `--date-from` and `--date-to` (`YYYY-MM-DD`).
- Base channel metrics (`title`, `username`, `participants_count`, `can_view_stats`, etc.).
- Post-level analytics (`views`, `forwards`, `replies`, `reactions`, `engagement_rate`).
- Correct publication-level counting for media albums (`grouped_id`) to avoid duplicated totals:
  photo albums are merged into one post, video messages stay separate posts.
- Advanced stats via Telegram Stats API when available.
- Explicit tracking of unavailable metrics (`no_access`, `private_stats`, etc.).
- Export to JSON and CSV + human-readable summary report.
- Persistent base file `stats_base.json` with full run history.

## Setup

If you download from GitHub:

```bash
git clone https://github.com/Navenienr/stats_for_tg.git
cd stats_for_tg
```

1. Create virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Optional: copy env template:

```bash
cp .env.example .env
```

3. You can either:
- provide values in `.env`, or
- enter them on first run interactively (recommended).

- `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
- `PHONE_NUMBER` in international format.

## Run

Simplest way for non-technical users (macOS):

```bash
./run.command
```

You can also double-click `run.command` in Finder.

Basic run:

```bash
python main.py
```

Every run now starts with a simple menu:

- `1` collect channel statistics,
- `2` reconfigure Telegram settings,
- `3` exit.

After that, interactive prompts ask:

- target channel (`@username`),
- period by number (`keep current`, `today`, `last 7 days`, `last 30 days`, `custom dates`).

The previously saved values are shown as defaults, and you can press Enter to keep them.
The script also remembers the last 10 used channel/date scopes and lets you pick one by entering its number.
At history selection step, you can also type a new `@channel` directly to start a new scope.
Use `--no-menu` if you want to skip the beginner menu and run directly.

Run setup again and rewrite saved defaults:

```bash
python main.py --reconfigure
```

Run with custom settings:

```bash
python main.py --channel @my_channel --date-from 2026-01-01 --date-to 2026-01-31 --post-limit 500 --output-dir exports_jan --save-settings
```

`--post-limit 0` means "collect all posts in selected date range" (default behavior).

ASCII tables are printed automatically after each collection run (friendly for non-technical users):

```bash
python main.py --ascii-top-posts 15
```

Disable ASCII tables if needed:

```bash
python main.py --no-ascii-table
```

## Output files

By default, files are written to `exports/`:

- `channels_stats.json` - full nested dataset.
- `channels_overview.csv` - one row per channel.
- `posts_metrics.csv` - one row per message/post.
- `unavailable_metrics.csv` - unavailable metrics with reasons.
- `summary.txt` - short text report.
- `stats_base.json` - separate persistent base file with full stats for each run.

By default, the script also prints:

- channel overview table (subscribers, posts, average views, average engagement),
- top posts table by views with short text preview.
- totals for selected period: posts, views, reposts, comments, reactions.

## Metrics map

| Metric | Source | Availability condition |
|---|---|---|
| `channel_id`, `channel_title`, `username`, `broadcast`, `megagroup`, `verified` | dialog/channel entity | available for resolved target channel |
| `participants_count`, `about`, `can_view_stats` | `channels.getFullChannel` | requires access to full channel info |
| `views`, `forwards`, `replies`, `reactions` | `iter_messages` | only posts inside selected date range |
| `engagement_rate` | derived from post metrics and participants | participants count must be known |
| `advanced_metrics` | `stats.getBroadcastStats` or `stats.getMegagroupStats` | requires Telegram stats permission for that channel |
| unavailable metric reason (`no_access`, `private_stats`) | local normalization | always available for failed/hidden fields |

## Notes and limitations

- Telegram does not expose every internal channel metric to every user.
- Some channels hide parts of stats; those fields are marked in `unavailable_metrics`.
- Large scans may trigger temporary rate limits; script retries after `FloodWait`.
- For album posts, multiple media items are normalized into one publication to keep totals realistic.

## Smoke test checklist

1. Run `python main.py`.
2. Complete Telegram login once (code + optional 2FA).
3. Verify that output files are created in output directory.
4. Open `unavailable_metrics.csv` and confirm inaccessible metrics are documented.
5. Re-run `python main.py` and confirm session is reused without new login code.
6. Confirm `user_settings.json` and `stats_base.json` are created and updated.
7. Verify validation errors are clear for bad range (`date_from > date_to`) or invalid channel format.
