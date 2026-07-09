#!/usr/bin/env python3
"""Daily token/cost snapshot for the acn-onboarding dashboard.

Fetches the analytics API (or imports a downloaded JSON file), transforms it
into a per-day snapshot, and appends/overwrites it in data/history.json.

Usage:
  python3 update.py                      # fetch API (days=1) using $ANALYTICS_COOKIE
  python3 update.py --file x.json        # import a manually downloaded JSON
  python3 update.py --date 2026-07-08    # override snapshot date (backfill/fix)
  python3 update.py --window 30          # override window_days (also API days param)
  python3 update.py --push               # git add + commit + push after saving

The cookie is read from the ANALYTICS_COOKIE environment variable and is
never written to disk.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://ai-analytics.wavemakeronline.com/api/v2/users"
TEAM = "acn-onboarding"
LIMIT = 100

ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / "data" / "history.json"

COOKIE_HELP = (
    "ANALYTICS_COOKIE is not set and no --file was given.\n"
    "Either:\n"
    "  1. Log in to https://ai-analytics.wavemakeronline.com in your browser,\n"
    "     copy the Cookie header from DevTools (Network tab -> any request ->\n"
    "     Request Headers -> Cookie), then run:\n"
    "       export ANALYTICS_COOKIE='<paste cookie here>'\n"
    "       python3 update.py --push\n"
    "  2. Or download the JSON response manually and import it:\n"
    "       python3 update.py --file response.json --push"
)


def fetch_api(cookie: str, days: int) -> dict:
    params = urllib.parse.urlencode(
        {"days": days, "team": TEAM, "limit": LIMIT, "_t": int(time.time() * 1000)}
    )
    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers={"Cookie": cookie, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            sys.exit(
                f"HTTP {e.code} from the analytics API — your session cookie has "
                "likely expired. Grab a fresh Cookie header from your browser's "
                "DevTools and re-export ANALYTICS_COOKIE."
            )
        sys.exit(f"HTTP {e.code} from the analytics API: {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach the analytics API: {e.reason}")


def load_source_file(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"File not found: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"{path} is not valid JSON: {e}")


def transform(payload: dict) -> list:
    """Map API chart_data entries to snapshot user records, sorted by cost desc."""
    if "chart_data" not in payload:
        sys.exit("Unexpected JSON shape: no 'chart_data' key (is this the /api/v2/users response?)")
    users = [
        {
            "email": entry["label"],
            "cost": entry["value"],
            "traces": entry["traces"],
            "url": entry.get("url"),
        }
        for entry in payload["chart_data"]
    ]
    users.sort(key=lambda u: u["cost"], reverse=True)
    return users


def load_history() -> dict:
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=1, sort_keys=True)
        f.write("\n")


def git_push(date: str) -> None:
    for cmd in (
        ["git", "add", "data/history.json"],
        ["git", "commit", "-m", f"snapshot {date}"],
        ["git", "push"],
    ):
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            sys.exit(f"Command failed: {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Save a daily usage snapshot to data/history.json")
    parser.add_argument("--file", help="import a downloaded API JSON file instead of calling the API")
    parser.add_argument("--date", help="snapshot date YYYY-MM-DD (default: today)")
    parser.add_argument("--window", type=int, default=1,
                        help="window_days to record; in API mode also the days= param (default: 1)")
    parser.add_argument("--push", action="store_true",
                        help="git add/commit/push data/history.json after saving")
    args = parser.parse_args()

    if args.date:
        try:
            date = datetime.date.fromisoformat(args.date).isoformat()
        except ValueError:
            sys.exit(f"--date must be YYYY-MM-DD, got: {args.date}")
    else:
        date = datetime.date.today().isoformat()

    if args.file:
        payload = load_source_file(args.file)
    else:
        cookie = os.environ.get("ANALYTICS_COOKIE")
        if not cookie:
            sys.exit(COOKIE_HELP)
        payload = fetch_api(cookie, args.window)

    users = transform(payload)
    history = load_history()
    history[date] = {"window_days": args.window, "users": users}
    save_history(history)

    total = sum(u["cost"] for u in users)
    print(f"{date}: {len(users)} users, ${total:.2f} total — {len(history)} day(s) in history.json")

    if args.push:
        git_push(date)


if __name__ == "__main__":
    main()
