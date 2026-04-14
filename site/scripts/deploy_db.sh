#!/usr/bin/env bash
# deploy-db.sh — copy local SQLite database to production and restart Gunicorn.
#
# Usage:
#   ./site/scripts/deploy-db.sh [--reset-database-posts-only] [user@host]
#
# Options:
#   --reset-database-posts-only
#       Delete all posts from the local DB and re-import from markdown before
#       deploying. Books, authors, and tags are not touched. Useful when you
#       only need to push post changes without a full reseed.
#
# The remote host can be supplied as a positional argument or set via the
# DEPLOY_HOST environment variable.
#
# Examples:
#   DEPLOY_HOST=root@1.2.3.4 ./site/scripts/deploy-db.sh
#   ./site/scripts/deploy-db.sh root@1.2.3.4
#   ./site/scripts/deploy-db.sh --reset-database-posts-only root@1.2.3.4

set -euo pipefail

# ── Load .env ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.env"
    set +a
fi

# ── Argument parsing ──────────────────────────────────────────────────────────

RESET_POSTS_ONLY=false
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --reset-database-posts-only)
            RESET_POSTS_ONLY=true
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

# ── Config ────────────────────────────────────────────────────────────────────

LOCAL_DB="site/instance/site.db"
REMOTE_DB="/var/www/book_reviews/site/instance/site.db"

# Resolve host: positional arg > DEPLOY_HOST env var > VPS_USER@VPS_HOST from .env
if [[ ${#POSITIONAL_ARGS[@]} -gt 0 ]]; then
    REMOTE_HOST="${POSITIONAL_ARGS[0]}"
elif [[ -n "${DEPLOY_HOST:-}" ]]; then
    REMOTE_HOST="$DEPLOY_HOST"
elif [[ -n "${VPS_USER:-}" && -n "${VPS_HOST:-}" ]]; then
    REMOTE_HOST="${VPS_USER}@${VPS_HOST}"
else
    REMOTE_HOST=""
fi

# ── Validation ────────────────────────────────────────────────────────────────

if [[ -z "$REMOTE_HOST" ]]; then
    echo "ERROR: no remote host supplied."
    echo "  Usage:  ./site/scripts/deploy-db.sh user@host"
    echo "  Or set: export DEPLOY_HOST=user@host"
    exit 1
fi

if [[ ! -f "$LOCAL_DB" ]]; then
    echo "ERROR: local database not found at '$LOCAL_DB'."
    echo "  Run 'make setup' or 'make reset' first."
    exit 1
fi

# ── Optional: reset posts ─────────────────────────────────────────────────────

if [[ "$RESET_POSTS_ONLY" == true ]]; then
    echo "==> Resetting posts in local database (books unchanged)"
    PYTHONPATH=site uv run flask --app site/app reset-posts --path writing/posts
    echo "==> Posts reset."
fi

# ── Deploy ────────────────────────────────────────────────────────────────────

echo "==> Copying database to ${REMOTE_HOST}:${REMOTE_DB}"
scp "$LOCAL_DB" "${REMOTE_HOST}:${REMOTE_DB}"

echo "==> Restarting Gunicorn on ${REMOTE_HOST} (clears in-process cache)"
ssh "$REMOTE_HOST" sudo systemctl restart gunicorn

echo "==> Done. Database deployed and cache cleared."