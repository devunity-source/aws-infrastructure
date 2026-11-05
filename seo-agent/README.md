# seo-agent

The SEO optimisation agent for Protocloud Reviews. This is Phase 2, slice 1: it imports the Search Console data and scores which articles to work on first.

It doesn't need any credentials. It runs on Python 3.11+ and needs only PyYAML, for post frontmatter. You'll need pytest to run the tests.

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
python -m seo_agent fetch --key key.json --site sc-domain:digitalapricot.io --days 90
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

## The move to digitalapricot.io

The blog moved from `protocloudsolutions.com/blog/` to the root of `digitalapricot.io` in November 2026.
`legacy_urls` in the config maps every old article URL to its new one. Scoring, the audit and the
dashboard group both URLs as one page, so an article's history carries across the move. Pages of the
consulting site are never counted as articles, because the host has to match. The weekly run fetches
both Search Console properties, `https://protocloudsolutions.com/` for the history and
`sc-domain:digitalapricot.io` from now on. If one property fails, for example before the service account
has access to it, the run logs a warning and carries on with the other.

## Weekly run on the server

`scripts/weekly.sh` runs everything in order: fetch new days, score a 28-day and a 90-day window,
and audit content. It's meant for cron on the web server. The repo is public, so search data never
goes through GitHub. The database, reports and logs live in `~/seo-agent-data` with owner-only
permissions.

Each run writes `~/seo-agent-data/reports/<date>/`, containing `opportunities-28d.md`,
`opportunities-90d.md` and `audit.md`, plus JSON versions. `reports/latest` points at the newest
one. Report folders older than 26 weeks are removed. The script pulls `main` first, so the agent
stays current. It skips the pull if that fails, and it won't run twice at once.

Setup, once, as the user that owns the checkout:

```bash
mkdir -p -m 700 ~/.config/seo-agent        # then put the service account key in gsc-key.json, chmod 600
crontab -e
# Mondays 06:17 UTC:
17 6 * * 1 $HOME/aws-infrastructure/seo-agent/scripts/weekly.sh >> $HOME/seo-agent-data/logs/weekly.log 2>&1
```

Run it by hand with `seo-agent/scripts/weekly.sh`. Settings come from environment variables
listed at the top of the script.

`score --days N` and `audit --days N` pick the latest import covering exactly N days. Use them
whenever several windows end on the same day.

## Dashboard

`dashboard --out DIR` writes one self-contained `index.html` with four views and a page per article:

- **Overview:** 28-day clicks, impressions, CTR and position against the previous 28 days, weekly
  charts, top opportunities and an audit summary.
- **Opportunities:** every scored page for the 28- or 90-day window, sortable, with a filter.
- **Audit:** every issue, filtered by severity or issue type.
- **Trends:** weekly site-wide charts, plus each page's last 4 full weeks against the 4 before.
- **Page view:** scores, the reasons behind them, weekly charts, audit issues, the searches that
  showed the page, and score history.

The page makes no external requests. Data is embedded as JSON that can't break out of its tag, every
Search Console string is escaped when shown, and the inline script is pinned by hash in a CSP meta tag.

The weekly run rebuilds it into `/var/www/html/seo-dashboard/`, and nginx serves it at
`https://digitalapricot.io/seo/` (and still `https://protocloudsolutions.com/seo/`) behind a password.
The `digitalapricot.io` server block includes the snippet. One-time setup on the server:

```bash
# Folder the weekly run writes and nginx reads
sudo install -d -o webserver -g www-data -m 2750 /var/www/html/seo-dashboard
# Password file (prompts for a password)
printf 'rakan:%s\n' "$(openssl passwd -apr1)" | sudo tee /etc/nginx/seo-dashboard.htpasswd >/dev/null
sudo chown root:www-data /etc/nginx/seo-dashboard.htpasswd && sudo chmod 640 /etc/nginx/seo-dashboard.htpasswd
# nginx: the snippet goes next to the blog's
sudo cp ~/aws-infrastructure/seo-agent/deploy/seo-dashboard.conf /etc/nginx/snippets/
sudo sed -i 's#^\(\s*\)include snippets/protocloud-blog.conf;#&\n\1include snippets/seo-dashboard.conf;#' \
  /etc/nginx/sites-available/protocloudsolutions.com
sudo nginx -t && sudo systemctl reload nginx
# First build
~/aws-infrastructure/seo-agent/scripts/weekly.sh
```

If the folder is missing or not writable, the weekly run skips the dashboard and still writes the reports.

## Product clicks (GA4)

Every product button on the blog sends a GA4 `affiliate_click` event with the product, ASIN,
link type (`product`, `search` or `retailer`), pick and position. Nothing about the reader is sent.
`ga4` counts those events per day, page and product with the GA4 Data API, using the same
service account key. The dashboard then shows product clicks on the overview, in the
Opportunities table, and per product on each page. These are clicks, not sales. Sales come from
Amazon Associates reports.

Setup, once:

1. In GA4 Admin > Property access management, add the service account's email as a **Viewer**.
2. In GA4 Admin > Custom definitions, add two **event-scoped** custom dimensions, for the
   parameters `product_name` and `asin`. Without them, clicks are still counted per page.
   GA4 only fills them in for events from the day they're created.
3. Find the numeric property ID in GA4 Admin > Property details. It is not the `G-` ID.
4. On the server, put it where cron can read it:

```bash
echo 'GA4_PROPERTY_ID=123456789' >> ~/.config/seo-agent/env && chmod 600 ~/.config/seo-agent/env
python3 -m seo_agent ga4 --property 123456789     # first run by hand, to check access
```

The weekly run fetches the last 120 days each time, because GA4 keeps processing recent days.
If GA4 fails, the run still finishes, and the dashboard keeps the clicks it already has.

## Content audit

```bash
python -m seo_agent audit --md out/audit.md --json out/audit.json
```

`audit` reads every post in the blog and checks it against fixed rules. Each issue has a severity
and the evidence behind it:

- **Search snippet:** title over 60 characters as rendered, description over 160 or under 70,
  a past year in the title.
- **Freshness:** no update in six months.
- **Images:** no hero image, or a hero image without alt text.
- **Links:** links to missing or retired pages, links through a redirect, orphan posts that nothing
  links to, fewer than two internal links.
- **Depth:** under 600 words, fewer than three sections, products with no ASIN or retailer URL.

If the database has an import, each post's opportunity score is joined in, which adds search
checks: impressions with no clicks, ranking beyond page 2, and stale-year searches. Pages changed
in the last 28 days get a "wait for data" note instead of "rewrite the title". Posts are ranked by
priority, which is issue severity weighted by opportunity. With no database, the audit checks
content only.

## Retired and redirected URLs

`score` and `audit` read the exact-match `return 410` and `return 301` rules in
`digitalapricot/deploy/protocloud-blog.conf`. Elsewhere, pass `--nginx` or set `SEO_AGENT_NGINX`.
Retired and redirected URLs are left out of scoring and listed separately, so they don't show up
as dead URLs.

## The dead URL check

`score` compares every scored URL against the blog's posts. Inside this repo it reads `digitalapricot/src/content/posts` automatically. Elsewhere, pass `--posts-dir` or set `SEO_AGENT_POSTS_DIR`. Pages without a post get the `dead_url` flag, because they return 404 or 410 unless a redirect covers them.

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
seo_agent/cli.py       import / sites / fetch / window / score / audit
seo_agent/content.py   post parser (frontmatter, headings, products, links) and nginx rules
seo_agent/audit.py     rule-based content audit joined with opportunity scores
seo_agent/gsc_api.py   Search Console API client: auth, pagination, retries
seo_agent/ga4_api.py   GA4 Data API client for product button clicks
seo_agent/dashboard.py static dashboard builder (templates/dashboard.html)
scripts/weekly.sh      weekly fetch, score, audit and dashboard for cron
deploy/                nginx snippet for the dashboard
tests/                 60 tests on synthetic data, with a fake API session (no real data, no network)
```
