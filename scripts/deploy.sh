#!/usr/bin/env bash

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai_vision}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
SERVICES="${DEPLOY_SERVICES:-}"

cd "$APP_DIR"

# Free disk space threshold (MB). If the root filesystem has less free space
# than this before we start, reclaim Docker space up front so the deploy does
# not die on a cryptic "No space left on device" during git fetch.
MIN_FREE_MB="${MIN_FREE_MB:-2048}"

free_mb() {
  df -Pm . | awk 'NR==2 {print $4}'
}

reclaim_docker_space() {
  echo "Reclaiming Docker space (unused images, containers, networks, build cache)..."
  docker system prune -af || true
  docker builder prune -af || true
}

echo "Current directory: $APP_DIR"

available_mb="$(free_mb)"
echo "Free disk space: ${available_mb}MB (minimum ${MIN_FREE_MB}MB)"
if [ "${available_mb:-0}" -lt "$MIN_FREE_MB" ]; then
  echo "Low disk space detected. Cleaning up before fetch..."
  reclaim_docker_space
  available_mb="$(free_mb)"
  echo "Free disk space after cleanup: ${available_mb}MB"
  if [ "${available_mb:-0}" -lt "$MIN_FREE_MB" ]; then
    echo "ERROR: Still under ${MIN_FREE_MB}MB free after cleanup. Free disk space on the droplet (e.g. 'docker system df', 'journalctl --vacuum-size=200M') and retry." >&2
    df -h . >&2
    exit 1
  fi
fi

echo "Fetching latest $REMOTE/$BRANCH..."

before="$(git rev-parse HEAD 2>/dev/null || true)"
git fetch "$REMOTE" "$BRANCH"
git reset --hard "$REMOTE/$BRANCH"
after="$(git rev-parse HEAD)"

changed_files=""
if [ -n "$before" ] && [ "$before" != "$after" ]; then
  changed_files="$(git diff --name-only "$before" "$after" || true)"
fi

echo "Changed files:"
if [ -n "$changed_files" ]; then
  printf '%s\n' "$changed_files"
else
  echo "No git code changes detected."
fi

mkdir -p models logs snapshots database

# Keep the droplet's disk from filling up over time. Cap the two directories
# that grow unbounded between deploys.
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"
SNAPSHOT_RETENTION_DAYS="${SNAPSHOT_RETENTION_DAYS:-3}"
echo "Rotating logs (>${LOG_RETENTION_DAYS}d) and snapshots (>${SNAPSHOT_RETENTION_DAYS}d)..."
find logs -type f -mtime "+${LOG_RETENTION_DAYS}" -delete 2>/dev/null || true
find snapshots -type f -mtime "+${SNAPSHOT_RETENTION_DAYS}" -delete 2>/dev/null || true
# Truncate any single log file that has grown past 100MB.
find logs -type f -size +100M -exec sh -c ': > "$1"' _ {} \; 2>/dev/null || true

if [ ! -f .env ]; then
  echo "No .env found. Creating from .env.example; edit it on the server for production secrets."
  cp .env.example .env
fi

build_required="false"
if [ -z "$before" ] || [ "$before" = "$after" ]; then
  build_required="false"
elif printf '%s\n' "$changed_files" | grep -Eq '(^Dockerfile$|^requirements.*\.txt$|^docker-compose\.yml$|^ai/|^api/|^cameras/|^database/|^detection/|^discovery/|^recognition/|^tracking/|^main\.py$)'; then
  build_required="true"
fi

if [ -n "$SERVICES" ]; then
  echo "Deploying requested service(s): $SERVICES"
  # shellcheck disable=SC2086
  docker compose up -d --build --remove-orphans $SERVICES
elif [ "$build_required" = "true" ]; then
  echo "Backend/runtime files changed. Rebuilding with Docker cache..."
  docker compose up -d --build --remove-orphans backend
else
  echo "Dashboard/config-only change. Rebuilding cheap app-code layer with Docker cache..."
  docker compose up -d --build --no-deps --force-recreate backend
fi

echo "Pruning unused Docker images and build cache..."
docker image prune -f || true
# Build cache accumulates on every 'docker compose --build' and 'docker image
# prune' does not touch it. Cap it so it cannot silently fill the disk.
docker builder prune -af --keep-storage 5GB 2>/dev/null || docker builder prune -af || true

echo "Deployment complete: $after"
