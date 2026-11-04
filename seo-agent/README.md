# seo-agent

The SEO optimisation agent for Protocloud Reviews. This is Phase 2, slice 1: it imports the Search Console data and scores which articles to work on first.

It doesn't need any credentials. It runs on Python 3.11+ and uses only the standard library. You'll need pytest to run the tests.

## Run it

```bash
cd seo-agent
python -m seo_agent import path/to/export.zip   # GSC UI export: zip, folder or single CSV
python -m seo_agent score --md out/opportunities.md --json out/scores.json
python -m pytest -q
```

Keep real exports and reports outside the repo, for example in `C:\Users\rakan\code\blog\gsc-exports`. The `.gitignore` here blocks `gsc-exports/`, `reports/`, zips and the SQLite file as a backstop.

GitHub Actions runs the tests on every pull request that touches `seo-agent/`.

You can run both commands again safely. An import that's already stored is skipped, because imports are matched by content hash. Rescoring the same import replaces its scores rather than adding new ones.

The database lives in `data/seo_agent.sqlite`. To use a different path, set `SEO_AGENT_DB` or pass `--db`.

## What the score means

Each article gets a score from 0 to 100. It's a weighted sum of five parts, each between 0 and 1. The weights live in `seo_agent/config.py`, and you can override them with `--config my.json`.

| Component | Weight | What it measures |
|---|---|---|
| visibility | 0.25 | Square root of impressions, capped at 1,500 |
| ctr_gap | 0.25 | How far CTR falls below a conservative baseline for its position. Damped below 200 impressions |
| position_band | 0.20 | 1.0 for positions 4 to 20. Lower when the page already ranks near the top or is past page 2 |
| commercial_intent | 0.15 | A best-of or vs slug, or the share of commercial queries |
| query_relevance | 0.15 | The share of inferred impressions that don't come from templated queries |

Every score comes with plain-English reasons. Flags: `dead_url` (no post with that slug in the blog), `zero_clicks`, `templated_queries`, `year_in_queries`, `possible_cannibalisation`, `declining` (needs two imports), `no_query_data`.

## Search Console API

The API removes the CSV limits: queries are joined to the pages they actually landed on,
page totals include anonymised traffic, and data is stored per day, so any window can be scored.

One-time setup:

1. In Google Cloud, enable the Google Search Console API and create a service account with a JSON key.
2. In Search Console, open Settings, Users and permissions, and add the service account's email.
   Restricted access is enough. Everything here is read-only.
3. Install the extra dependencies: `pip install -e '.[api]'`. On Ubuntu's system Python,
   `sudo apt install python3-google-auth python3-requests` works instead.

Then:

```bash
python -m seo_agent sites --key key.json                       # which properties the key can read
python -m seo_agent fetch --key key.json --site sc-domain:protocloudsolutions.com --days 90
python -m seo_agent window --days 90                           # aggregate stored days into an import
python -m seo_agent score --md out/opportunities.md
```

- `fetch` is incremental. It stores one day at a time, skips days already stored, and stops 3 days
  short of today because Search Console finalises data with a lag. Empty days from the last 10 days
  are fetched again on the next run, in case they weren't final yet. `--refetch` forces a refetch.
- Each day takes two calls: one grouped by query, for the query to page join, and one without query,
  for complete page totals.
- Network errors and HTTP 429 or 5xx are retried with backoff. A permission error says how to fix it.
- The key can also come from `GSC_SERVICE_ACCOUNT_JSON` (path or JSON content) or
  `GOOGLE_APPLICATION_CREDENTIALS`, and the site from `GSC_SITE`.
- When the latest import came from the API, `score` maps queries to pages from the observed data and
  says so. Reports from CSV imports still say "inferred".
- The `declining` flag only compares windows of the same length and source.

## The dead URL check

`score` compares every scored URL against the blog's posts. Inside this repo it reads `protocloud-reviews/src/content/posts` automatically. Elsewhere, pass `--posts-dir` or set `SEO_AGENT_POSTS_DIR`. Pages without a post get the `dead_url` flag, because they return 404 or 410 unless a redirect covers them.

## Known limits of CSV exports

The Search Console API path above removes these.

- The UI export has no query x page join. Any mapping of a query to a page is inferred from its wording and is labelled that way. Cannibalisation flags are leads to check, not findings.
- Anonymised queries are missing from Queries.csv. In the current export it covers 57% of impressions.
- Per-page trends need two imports, or the API's date dimension.
- The UI caps each table at 1,000 rows.

## Layout

```
seo_agent/gsc_csv.py   export parser (BOM, % CTR, header variants, zip or folder)
seo_agent/storage.py   SQLite schema, idempotent imports, API day storage and windows, score history
seo_agent/scoring.py   classification, templated-query detection, query->page inference, scoring
seo_agent/config.py    every tunable number, with comments
seo_agent/cli.py       import / sites / fetch / window / score
seo_agent/gsc_api.py   Search Console API client: auth, pagination, retries
tests/                 46 tests on synthetic data, with a fake API session (no real data, no network)
```
