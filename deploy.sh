#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-help}"

note() { echo "[deploy] $*"; }
die() { echo "[deploy] ERROR: $*" >&2; exit 1; }

require_tools() {
  command -v docker >/dev/null 2>&1 || die "Docker not found"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 not found (docker compose)"
}

init() {
  note "Starting databases: postgres, redis"
  docker compose up -d postgres redis
}

migrate() {
  note "Running Alembic migrations"
  docker compose run --rm api alembic -c alembic.ini upgrade head
}

start() {
  note "Starting services: api, worker, beat, prometheus"
  docker compose up -d api worker beat prometheus
}

up() {
  init
  migrate
  start
}

update() {
  note "Building images and applying updates"
  docker compose build --no-cache
  docker compose up -d
  migrate
}

status() {
  docker compose ps
}

logs() {
  docker compose logs --tail=200 -f api worker beat
}

down() {
  note "Stopping services (preserving volumes)"
  docker compose down
}

destroy() {
  note "Stopping services and removing volumes (DATA LOSS)"
  docker compose down -v
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
