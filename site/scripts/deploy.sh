#!/usr/bin/env bash
# deploy.sh — Deploy book-reviews to the production VPS.
#
# Usage:
#   ./deploy.sh                  # pull latest code, import posts, restart
#   ./deploy.sh --reset-database # wipe and rebuild DB, then sync everything
#
# Required environment variables (set in .env or export before running):
#   VPS_HOST        IP or hostname of the VPS            e.g. 192.0.2.10
#   VPS_USER        SSH user                             e.g. root
#   VPS_PASSWORD    SSH password (used via sshpass)
#   LOCAL_POSTS_DIR Absolute path to local posts folder  e.g. /home/me/posts
#
# Optional:
#   VPS_REPO_DIR    Path to repo root on VPS (default: /var/www/book_reviews)

set -euo pipefail

# ── Load .env if present ────────────────────────────────────────────────────
# Search order: next to the script, then walk up to the repo root.
# The script lives at  <repo>/site/scripts/deploy.sh
# so the repo root is  <repo>/  (two levels up).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE=""
for candidate in "${SCRIPT_DIR}/.env" "${REPO_ROOT}/.env"; do
    if [[ -f "$candidate" ]]; then
        ENV_FILE="$candidate"
        break
    fi
done

if [[ -n "$ENV_FILE" ]]; then
    echo "Loading environment from: ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "WARNING: No .env file found (looked in ${SCRIPT_DIR} and ${REPO_ROOT})." >&2
    echo "         Falling back to already-exported environment variables." >&2
fi

# ── Validate required vars ───────────────────────────────────────────────────
missing=()
for var in VPS_HOST VPS_USER VPS_PASSWORD LOCAL_POSTS_DIR; do
    [[ -z "${!var:-}" ]] && missing+=("$var")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    echo "ERROR: Missing required environment variables: ${missing[*]}" >&2
    echo "       Set them in .env or export them before running this script." >&2
    exit 1
fi

VPS_REPO_DIR="${VPS_REPO_DIR:-/var/www/book_reviews}"
RESET_DATABASE=false

# ── Parse arguments ──────────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --reset-database) RESET_DATABASE=true ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

# ── Dependency check ─────────────────────────────────────────────────────────
if ! command -v sshpass &>/dev/null; then
    echo "ERROR: 'sshpass' is not installed." >&2
    echo "       Install it with: brew install sshpass  OR  sudo apt install sshpass" >&2
    exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o BatchMode=no)
# Export for sshpass
export SSHPASS="$VPS_PASSWORD"

run_ssh() {
    # Run a command on the VPS, printing it first
    local cmd="$1"
    echo "  → $cmd"
    sshpass -e ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" "$cmd"
}

# ── Step 1: Copy posts ───────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
echo " Step 1: Copying posts to VPS"
echo "═══════════════════════════════════════════"

REMOTE_POSTS_DIR="${VPS_REPO_DIR}/site/content/posts"

# Ensure the remote posts directory exists
run_ssh "mkdir -p ${REMOTE_POSTS_DIR}"

echo "  → scp -r ${LOCAL_POSTS_DIR}/ ${VPS_USER}@${VPS_HOST}:${REMOTE_POSTS_DIR}/"
sshpass -e scp "${SSH_OPTS[@]}" -r "${LOCAL_POSTS_DIR}/." "${VPS_USER}@${VPS_HOST}:${REMOTE_POSTS_DIR}/"
echo "  ✓ Posts copied."

# ── Step 2: Pull latest code ─────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
echo " Step 2: Pulling latest code on VPS"
echo "═══════════════════════════════════════════"

run_ssh "cd ${VPS_REPO_DIR} && git pull"
echo "  ✓ Code updated."

# ── Step 3: Database setup or sync ───────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
if [[ "$RESET_DATABASE" == true ]]; then
    echo " Step 3: Resetting database and syncing"
    echo "═══════════════════════════════════════════"
    echo "  ⚠ WARNING: This will wipe the production database!"
    read -rp "  Are you sure? Type 'yes' to continue: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "  Aborted."
        exit 0
    fi
    run_ssh "cd ${VPS_REPO_DIR} && make setup"
    echo "  ✓ Database reset."
else
    echo " Step 3: Syncing books and posts"
    echo "═══════════════════════════════════════════"
fi

run_ssh "cd ${VPS_REPO_DIR} && make sync"
echo "  ✓ Sync complete."

# ── Step 4: Restart Gunicorn ─────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════"
echo " Step 4: Restarting Gunicorn"
echo "═══════════════════════════════════════════"

run_ssh "sudo systemctl restart gunicorn"
echo "  ✓ Gunicorn restarted."

echo
echo "✅ Deploy complete."