# telemetry-board

Crypto Telemetry Board — FastAPI + Celery + Postgres + Redis + Prometheus.

## Szybkie uruchomienie (Ubuntu)

Wymagania: Docker, Docker Compose, Python 3.11 (opcjonalnie dla pracy lokalnej), make.

```bash
git clone <repo-url> telemetry-board
cd telemetry-board

# Podnieś cały stack lokalny
make compose-up

# Zdrowie API
curl http://localhost:8000/health # => {"status":"ok"}

# Prometheus (opcjonalnie)
# przeglądarka: http://localhost:9090/targets
```

Zatrzymanie i sprzątanie:

```bash
make compose-down
```

## Praca deweloperska (lokalnie)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
pip install pre-commit ruff mypy pytest

# Jakość
make lint
make typecheck
make test

# API (lokalnie)
uvicorn app.main:app --reload --port 8000

# Worker (lokalnie)
celery -A worker.worker_app.celery_app worker --loglevel=info
```

## Konfiguracja

- `DATABASE_URL`, `REDIS_URL` — łańcuchy połączeń (w compose ustawione na kontenery).
- `ENABLE_METRICS_ENDPOINT` — włącza `/metrics` w API.
- `ENABLE_WORKER_METRICS` i `WORKER_METRICS_PORT` — eksport metryk workera.

## Metryki

- API: `/metrics` (tekst Prometheusa). Zliczane są: `api_requests_total`, `api_request_duration_seconds`.
- Worker: endpoint HTTP uruchamiany przez `prometheus_client.start_http_server` (domyślnie port 8001).

## Licencja

MIT
