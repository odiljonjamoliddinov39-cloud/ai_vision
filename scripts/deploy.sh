#!/usr/bin/env bash

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai_vision}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
SERVICES="${DEPLOY_SERVICES:-}"

cd "$APP_DIR"

echo "Current directory: $APP_DIR"
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

if [ ! -f .env ]; then
  echo "No .env found. Creating from .env.example; edit it on the server for production secrets."
  cp .env.example .env
fi

build_required="false"
if [ -z "$before" ] || [ "$before" = "$after" ]; then
  build_required="false"
elif printf '%s\n' "$changed_files" | grep -Eq '(^Dockerfile$|^requirements.*\.txt$|^docker-compose\.yml$|^ai/|^api/|^cameras/|^database/|^detection/|^recognition/|^tracking/|^main\.py$)'; then
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
  echo "Dashboard/config-only change. Recreating backend without dependency reinstall..."
  docker compose up -d --no-deps --force-recreate backend
fi

echo "Pruning unused Docker images..."
docker image prune -f

echo "Deployment complete: $after"
