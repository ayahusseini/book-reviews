#!/usr/bin/env bash
# deploy-db.sh — copy local SQLite database to production and restart Gunicorn.
#
# Usage:
#   ./site/scripts/deploy-db.sh [user@host]
#
# The remote host can be supplied as an argument or set via the DEPLOY_HOST
# environment variable. If neither is provided the script will exit with an
# error.
#
# Examples:
#   DEPLOY_HOST=root@1.2.3.4 ./site/scripts/deploy-db.sh
#   ./site/scripts/deploy-db.sh root@1.2.3.4

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

LOCAL_DB="site/instance/site.db"
REMOTE_DB="/var/www/book_reviews/site/instance/site.db"
REMOTE_HOST="${1:-${DEPLOY_HOST:-}}"


# ── Validation ────────────────────────────────────────────────────────────────

if [[ -z "$REMOTE_HOST" ]]; then
    echo "ERROR: no remote host supplied."
    echo "  Usage:  ./site/scripts/deploy-db.sh user@host"
    echo "  Or set: export DEPLOY_HOST=user@host"
    exit 1
fi

if [[ ! -f "$LOCAL_DB" ]]; then
    echo "ERROR: local database not found at '$LOCAL_DB'."
    echo "  Run 'make setup' or 'make seed' first."
    exit 1
fi

# ── Deploy ────────────────────────────────────────────────────────────────────

echo "==> Copying database to ${REMOTE_HOST}:${REMOTE_DB}"
scp "$LOCAL_DB" "${REMOTE_HOST}:${REMOTE_DB}"

echo "==> Restarting Gunicorn on ${REMOTE_HOST} (clears in-process cache)"
ssh "$REMOTE_HOST" sudo systemctl restart gunicorn

echo "==> Done. Database deployed and cache cleared."