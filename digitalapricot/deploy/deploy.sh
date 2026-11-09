#!/usr/bin/env bash
# Build Digital Apricot and rsync it to the nginx box.
# Usage: DEPLOY_HOST=user@1.2.3.4 ./deploy/deploy.sh
#   DEPLOY_HOST  ssh target (required)
#   DEPLOY_PATH  web root on the server (default /var/www/html/digitalapricot)
#   SSH_KEY      optional path to a private key
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DEPLOY_HOST:?Set DEPLOY_HOST, e.g. ubuntu@203.0.113.10}"
DEPLOY_PATH="${DEPLOY_PATH:-/var/www/html/digitalapricot}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
[[ -n "${SSH_KEY:-}" ]] && SSH_OPTS+=(-i "$SSH_KEY")

if ! grep -qE "CLIENT: 'ca-pub-[0-9]{16}'" src/lib/site.ts; then
  echo "warning: AdSense publisher ID is still the placeholder in src/lib/site.ts, ads will not render" >&2
fi

npm ci
npm run build

Q_PATH=$(printf '%q' "$DEPLOY_PATH")
ssh "${SSH_OPTS[@]}" -- "$DEPLOY_HOST" "sudo mkdir -p $Q_PATH && sudo chown -R \$(id -un) $Q_PATH"
RSYNC_SSH=$(printf '%q ' ssh "${SSH_OPTS[@]}")
rsync -az --delete -e "$RSYNC_SSH" dist/ "$DEPLOY_HOST:$DEPLOY_PATH/"
echo "deployed to $DEPLOY_HOST:$DEPLOY_PATH"
