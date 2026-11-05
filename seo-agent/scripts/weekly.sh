#!/usr/bin/env bash
# Weekly SEO run: fetch new Search Console days, score 28- and 90-day windows, audit content.
# Built for cron on the web server. Data and reports stay on this machine and are never pushed.
#
#   SEO_AGENT_REPO        repo checkout            (default ~/aws-infrastructure)
#   SEO_AGENT_HOME        data, reports and logs    (default ~/seo-agent-data)
#   GSC_SITE              Search Console properties, space-separated
#                         (default: https://protocloudsolutions.com/ sc-domain:digitalapricot.io)
#   GSC_SERVICE_ACCOUNT_JSON  key file              (default ~/.config/seo-agent/gsc-key.json)
#   SEO_AGENT_KEEP_WEEKS  report folders to keep    (default 26)
#   SEO_DASHBOARD_DIR     where the dashboard goes  (default /var/www/html/seo-dashboard)
#   GA4_PROPERTY_ID       numeric GA4 property, for product button clicks (optional; skipped if unset)
#   SEO_AGENT_SKIP_PULL=1 don't update the checkout (for testing)
#
# Cron doesn't read ~/.bashrc, so any of these can also go in ~/.config/seo-agent/env,
# one VAR=value per line. That file is read first if it exists.
set -euo pipefail

ENV_FILE="${SEO_AGENT_ENV:-$HOME/.config/seo-agent/env}"
# shellcheck source=/dev/null
[ -r "$ENV_FILE" ] && . "$ENV_FILE"

REPO="${SEO_AGENT_REPO:-$HOME/aws-infrastructure}"
DATA="${SEO_AGENT_HOME:-$HOME/seo-agent-data}"
# The old property holds the blog's history before the move; the new one everything after.
SITES="${GSC_SITE:-https://protocloudsolutions.com/ sc-domain:digitalapricot.io}"
KEEP_WEEKS="${SEO_AGENT_KEEP_WEEKS:-26}"
export GSC_SERVICE_ACCOUNT_JSON="${GSC_SERVICE_ACCOUNT_JSON:-$HOME/.config/seo-agent/gsc-key.json}"
export SEO_AGENT_DB="$DATA/seo_agent.sqlite"

umask 077  # search data is private: owner-only files
mkdir -p "$DATA/reports" "$DATA/logs"

# One run at a time.
exec 9>"$DATA/.lock"
flock -n 9 || { echo "another run is in progress, skipping"; exit 0; }

if [ ! -r "$GSC_SERVICE_ACCOUNT_JSON" ]; then
  echo "error: key not found at $GSC_SERVICE_ACCOUNT_JSON" >&2
  exit 2
fi

# Keep the agent current. If the pull fails (network, local changes), run the code we have.
if [ "${SEO_AGENT_SKIP_PULL:-0}" != "1" ]; then
  git -C "$REPO" pull -q --ff-only origin main || echo "warning: git pull failed, using the current code"
fi

out="$DATA/reports/$(date -u +%F)"
mkdir -p "$out"
cd "$REPO/seo-agent"
agent() { python3 -m seo_agent "$@"; }

# Incremental: only new days are fetched. One property failing (e.g. no access yet) doesn't stop the run.
fetched=0
for site in $SITES; do
  if agent fetch --site "$site" --days 120; then fetched=1; else echo "warning: fetch failed for $site"; fi
done
[ "$fetched" = 1 ] || { echo "error: no Search Console property could be fetched" >&2; exit 2; }
agent window --days 28
agent score --days 28 --top 30 --md "$out/opportunities-28d.md" --json "$out/scores-28d.json"
agent window --days 90
agent score --days 90 --top 40 --md "$out/opportunities-90d.md" --json "$out/scores-90d.json"
agent audit --days 90 --md "$out/audit.md" --json "$out/audit.json"

# Product button clicks from GA4. Optional, and a GA4 problem never fails the run.
if [ -n "${GA4_PROPERTY_ID:-}" ]; then
  agent ga4 --property "$GA4_PROPERTY_ID" --days 120 || echo "warning: GA4 fetch failed, the dashboard keeps the last clicks"
else
  echo "note: GA4_PROPERTY_ID is not set, so product clicks were skipped"
fi

# The dashboard is served by nginx, so it goes outside the private data folder.
# A dashboard problem never fails the run: the reports above are already written.
dash="${SEO_DASHBOARD_DIR:-/var/www/html/seo-dashboard}"
if [ -d "$dash" ] && [ -w "$dash" ]; then
  agent dashboard --out "$dash" || echo "warning: dashboard build failed"
else
  echo "note: $dash is missing or not writable, so the dashboard was skipped"
fi

ln -sfn "$out" "$DATA/reports/latest"
find "$DATA/reports" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$((KEEP_WEEKS * 7))" -exec rm -rf {} +
echo "$(date -u +%FT%TZ) weekly run ok: $out"
