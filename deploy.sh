#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-help}"

note() { echo "[deploy] $*"; }
die() { echo "[deploy] ERROR: $*" >&2; exit 1; }

require_tools() {
  command -v docker >/dev/null 2>&1 || die "Docker not found"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 not found (docker compose)"
}

# Wrapper around docker compose that supports optional overrides via
# DEPLOY_OVERRIDES (e.g. "-f ops/compose.tunnel.yml -f ops/compose.prometheus-auth.yml").
dc() {
  # shellcheck disable=SC2086
  docker compose ${DEPLOY_OVERRIDES:-} "$@"
}

init() {
  note "Starting databases: postgres, redis"
  dc up -d postgres redis
}

migrate() {
  note "Running Alembic migrations"
  dc run --rm api alembic -c alembic.ini upgrade head
}

start() {
  note "Starting services: api, worker, beat, prometheus"
  dc up -d api worker beat prometheus
}

up() {
  init
  migrate
  start
}

update() {
  note "Building images and applying updates"
  dc build --no-cache
  dc up -d
  migrate
}

status() {
  dc ps
}

logs() {
  dc logs --tail=200 -f api worker beat
}

down() {
  note "Stopping services (preserving volumes)"
  dc down
}

destroy() {
  note "Stopping services and removing volumes (DATA LOSS)"
  dc down -v
}

help() {
  cat <<EOF
Usage: ./deploy.sh <command>

Commands:
  up        Start postgres+redis, run migrations, start services
  init      Start postgres+redis only
  migrate   Run Alembic migrations
  start     Start api, worker, beat, prometheus
  update    Rebuild images, restart, run migrations
  status    Show container status
  logs      Tail logs for api/worker/beat
  down      Stop services (keep data volumes)
  destroy   Stop services and remove volumes (DATA LOSS)
  help      Show this help
EOF
}

main() {
  require_tools
  case "$cmd" in
    up) up ;;
    init) init ;;
    migrate) migrate ;;
    start) start ;;
    update) update ;;
    status) status ;;
    logs) logs ;;
    down) down ;;
    destroy) destroy ;;
    help|*) help ;;
  esac
}

main "$@"
