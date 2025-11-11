# Repository Guidelines

## Project Structure & Module Organization
`app/` holds the FastAPI service: keep transport logic in `api/`, core rules in `core/`, persistence helpers in `db/`, telemetry glue in `metrics/`, and SQLAlchemy models in `models/`, while `main.py` exposes the ASGI entrypoint. `worker/` provides the Celery app plus background jobs under `worker/tasks/`; keep them HTTP-agnostic. `tests/` mirrors the package layout for pytest coverage, and `ops/` with the compose file and Dockerfiles defines the local stack (API, worker, Postgres, Redis, Prometheus).

## Build, Test, and Development Commands
Set up a virtualenv, then run `python -m pip install -e . && pip install pre-commit ruff mypy pytest` to get runtime plus tooling. Use `uvicorn app.main:app --reload --port 8000` for the API, `celery -A worker.worker_app.celery_app worker --loglevel=info` for async jobs, and `docker compose up --build` when you need the full telemetry stack. Validate changes with `python -m pytest -q` and the lint/type pipeline `ruff check . && ruff format . && mypy app worker tests`.

## Coding Style & Naming Conventions
Code targets Python 3.11 with 4-space indentation and 100-character lines enforced by Ruff’s formatter. Modules, functions, and async tasks stay in `snake_case`, classes in `PascalCase`, constants and env keys in `UPPER_SNAKE_CASE`. Type hints are mandatory (`disallow_untyped_defs` is enabled), and `pre-commit run --all-files` should be clean before you push.

## Testing Guidelines
Author pytest files as `tests/test_<feature>.py`, keep function names descriptive (`test_health_ok`), and rely on FastAPI’s `TestClient` or Celery doubles so tests stay isolated from live services. Aim for roughly 80 % branch coverage on new work and always add regression cases when fixing bugs or extending worker tasks. Isolate external APIs or databases with fixtures so CI on GitHub Actions stays deterministic.

## Commit & Pull Request Guidelines
Follow the existing history of conventional prefixes (`feat:`, `fix:`, `chore:`, `test:`) and keep subjects under ~60 characters, expanding context in the body if needed. Pull requests must explain the change, list verification steps (`pytest`, `ruff`, `mypy`, compose smoke check), and link issues or screenshots/logs when metrics outputs change. Run a final self-review before requesting feedback.

## Security & Configuration Tips
Secrets such as database credentials or API tokens belong in `.env` or your orchestration layer; reference them via `DATABASE_URL`, `REDIS_URL`, and similar settings and never commit plaintext values. Keep `/metrics` endpoints reachable only from the internal compose/cluster network and let Prometheus handle scraping instead of exposing them publicly.
