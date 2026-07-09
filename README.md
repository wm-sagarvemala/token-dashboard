# Token Usage Dashboard — acn-onboarding

Zero-backend daily cost/traces dashboard for the `acn-onboarding` team, hosted on
GitHub Pages and refreshed once a day by `update.py` (~10 seconds of maintenance).

> "Token usage" is reported as **cost ($)** and **traces** — the analytics API
> does not expose raw token counts.

## Architecture

```
Sagar's login (browser cookie)
        │ once a day
        ▼
update.py ── GET analytics API (days=1) ──► append snapshot to data/history.json ──► git commit + push
                                                                                          │
GitHub Pages serves static files: index.html + data/history.json ◄────────────────────────┘
                                        │
                        Team opens URL, selects any day, views charts/table
```

- `data/history.json` **is** the database: two named snapshots (`last24hours`,
  `last30days`, each with an `updated_at` timestamp) plus a `daily` map of
  per-day totals that feeds the trend chart. The dashboard shows a
  Last 30 days / Last 24 hours toggle and defaults to the freshest snapshot.
- Costs are also shown as platform credits (1 USD = 20 credits).
- No server, no build step, no framework — plain HTML/CSS/JS + Chart.js from CDN.
- No auth on the dashboard itself; repo/Pages visibility controls access.

## One-time setup

1. Create a GitHub repository (e.g. `token-dashboard`) and push this directory:

   ```sh
   git init
   git add .
   git commit -m "initial dashboard"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. Enable GitHub Pages: repo **Settings → Pages → Source: Deploy from a branch →
   Branch: `main` / `(root)` → Save**.

3. Share the Pages URL (`https://<owner>.github.io/token-dashboard/`) with the team.

**Privacy note:** the dashboard shows teammates' emails and spend. GitHub Pages
sites from **private repos require GitHub Enterprise Cloud**; on other plans a
Pages site is publicly reachable at its URL even if the repo is private. Pick
repo visibility (and whether Pages is acceptable) accordingly — an internal/org
repo with access-controlled Pages is the safe default.

## Getting the cookie (for `update.py`)

1. Log in to `https://ai-analytics.wavemakeronline.com` in your browser.
2. Open DevTools → **Network** tab → click any request to the site.
3. Under **Request Headers**, copy the entire `Cookie` value.
4. In your terminal:

   ```sh
   export ANALYTICS_COOKIE='<paste the cookie here>'
   ```

The cookie lives only in that shell's environment — it is never written to disk
or committed. When the API starts returning 401/403, the session expired: repeat
these steps.

## The daily 10-second routine

```sh
cd token-dashboard
# Option A: import the JSON you downloaded from the analytics site
python3 update.py --file ~/Downloads/Last24Hours.json --push

# Option B: fetch directly from the API
export ANALYTICS_COOKIE='<cookie>'    # only when the previous one expired
python3 update.py --push
```

Either way this refreshes the **Last 24 hours** snapshot (with an updated
timestamp), records today's totals in the trend, commits, and pushes. Pages
redeploys automatically within a minute or two.

To refresh the **Last 30 days** snapshot, add `--window 30` (with `--file` it
just marks the import as 30-day data; without it, it fetches `days=30`):

```sh
python3 update.py --window 30 --push
python3 update.py --file Last30Days.json --window 30 --push
```

## Backfill / fix a day in the trend

```sh
# Overwrite a specific trend date (idempotent — re-running replaces, never duplicates)
python3 update.py --file older-export.json --date 2026-07-08 --push
```

## Local preview

```sh
cd token-dashboard
python3 -m http.server
# open http://localhost:8000
```

Opening `index.html` via `file://` will NOT work — the dashboard fetches
`data/history.json`, which browsers block on the `file://` scheme.

## Snapshot reminder (optional)

`.github/workflows/snapshot-reminder.yml` runs daily and opens a GitHub issue
titled "Token snapshot missing for <date>" if yesterday has no entry in
`history.json`. It cannot fetch the API itself (the session cookie can't be
shared with CI) — it's only a nudge. Delete the file if you don't want it.

## Decommissioning

This is an interim solution until the backend team ships a real team dashboard.
When that lands: archive this repo (Settings → Archive) and point the team at
the new URL. Nothing else to tear down — there is no server or database.
