#!/usr/bin/env bash
# Weekly SEO run: fetch new Search Console days, score 28- and 90-day windows, audit content.
# Built for cron on the web server. Data and reports stay on this machine and are never pushed.
#
#   SEO_AGENT_REPO        repo checkout            (default ~/aws-infrastructure)
#   SEO_AGENT_HOME        data, reports and logs    (default ~/seo-agent-data)
#   GSC_SITE              Search Console property   (default https://protocloudsolutions.com/)
#   GSC_SERVICE_ACCOUNT_JSON  key file              (default ~/.config/seo-agent/gsc-key.json)
#   SEO_AGENT_KEEP_WEEKS  report folders to keep    (default 26)
#   SEO_AGENT_SKIP_PULL=1 don't update the checkout (for testing)
set -euo pipefail

REPO="${SEO_AGENT_REPO:-$HOME/aws-infrastructure}"
DATA="${SEO_AGENT_HOME:-$HOME/seo-agent-data}"
SITE="${GSC_SITE:-https://protocloudsolutions.com/}"
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

agent fetch --site "$SITE" --days 120          # incremental: only new days are fetched
agent window --days 28
agent score --days 28 --top 30 --md "$out/opportunities-28d.md" --json "$out/scores-28d.json"
agent window --days 90
agent score --days 90 --top 40 --md "$out/opportunities-90d.md" --json "$out/scores-90d.json"
agent audit --days 90 --md "$out/audit.md" --json "$out/audit.json"

ln -sfn "$out" "$DATA/reports/latest"
find "$DATA/reports" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$((KEEP_WEEKS * 7))" -exec rm -rf {} +
echo "$(date -u +%FT%TZ) weekly run ok: $out"
