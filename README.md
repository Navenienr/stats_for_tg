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
- Advanced stats via Telegram Stats API when available.
- Explicit tracking of unavailable metrics (`no_access`, `private_stats`, etc.).
- Export to JSON and CSV + human-readable summary report.
- Persistent base file `stats_base.json` with full run history.

## Setup

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

Basic run:

```bash
python main.py
```

Run setup again and rewrite saved defaults:

```bash
python main.py --reconfigure
```

Run with custom settings:

```bash
python main.py --channel @my_channel --date-from 2026-01-01 --date-to 2026-01-31 --post-limit 500 --output-dir exports_jan --save-settings
```

## Output files

By default, files are written to `exports/`:

- `channels_stats.json` - full nested dataset.
- `channels_overview.csv` - one row per channel.
- `posts_metrics.csv` - one row per message/post.
- `unavailable_metrics.csv` - unavailable metrics with reasons.
- `summary.txt` - short text report.
- `stats_base.json` - separate persistent base file with full stats for each run.

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

## Smoke test checklist

1. Run `python main.py`.
2. Complete Telegram login once (code + optional 2FA).
3. Verify that output files are created in output directory.
4. Open `unavailable_metrics.csv` and confirm inaccessible metrics are documented.
5. Re-run `python main.py` and confirm session is reused without new login code.
6. Confirm `user_settings.json` and `stats_base.json` are created and updated.
7. Verify validation errors are clear for bad range (`date_from > date_to`) or invalid channel format.
