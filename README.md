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

## Deployment (pierwsze wdrożenie na serwerze)

Prosty, przewidywalny proces bez dodatkowych narzędzi — tylko Docker Compose.

1) Wymagania na serwerze
- Zainstalowany Docker i Docker Compose.
- Dostęp SSH, otwarty port 8000 (API). Port 9090 (Prometheus) tylko w sieci zaufanej lub zablokowany.

2) Pobranie repo i przygotowanie
```bash
git clone <repo-url> telemetry-board
cd telemetry-board
```

3) Uruchom bazy danych
```bash
docker compose up -d postgres redis
```

4) Migracje schematu (Alembic)
```bash
docker compose run --rm api alembic -c alembic.ini upgrade head
```

5) Start usług
```bash
docker compose up -d api worker beat prometheus
```

6) Smoke-check
- API: `curl http://localhost:8000/health` → `{ "status": "ok" }`
- Logi: `docker compose logs -f api worker beat`
- Prometheus (opcjonalnie): `http://localhost:9090/targets`

Aktualizacja wdrożenia:
```bash
git pull
docker compose build --no-cache
docker compose up -d
docker compose run --rm api alembic -c alembic.ini upgrade head
```

Wyłączenie usług:
```bash
docker compose down
```

Uwaga: zmienne środowiskowe są ustawione w `docker-compose.yml`. W razie potrzeby możesz utworzyć `.env` z nadpisaniami (np. `ENABLE_METRICS_ENDPOINT=false` dla prod).

## Prosty CD (GitHub Actions + self-hosted runner)

Jeśli chcesz automatycznie wdrażać zmiany z gałęzi `main` na serwer:

1) Na serwerze z Dockerem zainstaluj self-hosted runnera GitHub i nadaj mu label `prod`.
2) Upewnij się, że runner ma dostęp do Dockera (grupa `docker`).
3) W repo jest workflow `.github/workflows/cd.yml`, który na `push` do `main` wykona `./deploy.sh update` na runnerze.

Ręczne wywołanie (manual trigger) jest dostępne przez `workflow_dispatch`.

### Skróty: deploy.sh

Repo zawiera prosty skrypt ułatwiający standardowe operacje:

```bash
./deploy.sh up       # bazy → migracje → start usług
./deploy.sh update   # rebuild → restart → migracje
./deploy.sh status   # status kontenerów
./deploy.sh logs     # logi api/worker/beat
./deploy.sh down     # zatrzymanie (bez kasowania wolumenów)
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

## Konfiguracja backendu

- API
  - `ENABLE_METRICS_ENDPOINT` — odsłania `/metrics` (domyślnie: wyłączone).
- Worker/Beat
  - `ENABLE_BEAT` — włącza harmonogram zadań (fetch/prune/alerts).
  - `ASSETS` — lista symboli do pobierania, np. `BTC,ETH`.
  - `FETCH_INTERVAL_SECONDS` — interwał pobierania cen (domyślnie: 300).
  - `ALERT_WINDOW_MINUTES` — okno liczenia alertów (domyślnie: 60).
  - `ALERT_THRESHOLD_PCT` — próg alertu w % (domyślnie: 5).
  - Retencja: `RETENTION_DAYS` — ile dni trzymać próbki (domyślnie: 30; ustaw `0`, aby wyłączyć sprzątanie) oraz
    `RETENTION_INTERVAL_SECONDS` — jak często uruchamiać sprzątanie (domyślnie: 86400 = 1 dzień).
    Zadanie `prune_old_prices` usuwa rekordy starsze niż `RETENTION_DAYS` — pomocne, by kontrolować zużycie dysku.

## Metryki

- API: `/metrics` (tekst Prometheusa). Zliczane są: `api_requests_total`, `api_request_duration_seconds`.
- Worker: endpoint HTTP uruchamiany przez `prometheus_client.start_http_server` (domyślnie port 8001).

## Licencja

MIT
