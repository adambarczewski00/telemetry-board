# telemetry-board

Crypto Telemetry Board — FastAPI + Celery + Postgres + Redis + Prometheus.

Materiały dla rekrutera: zobacz prezentację projektu w `docs/PRESENTATION.md` oraz diagramy przepływu w `docs/DIAGRAMS.md`.

## Szybkie uruchomienie (Ubuntu)

Wymagania: Docker, Docker Compose, Python 3.11 (opcjonalnie dla pracy lokalnej), make.

```bash
git clone <repo-url> telemetry-board
cd telemetry-board

# Podniesienie całego stacku lokalnie
make compose-up

# Zdrowie API
curl http://localhost:8000/health  # => {"status":"ok"}

# Prometheus (opcjonalnie)
# przeglądarka: http://localhost:9090/targets
```

## Szybki start: Cloudflare Tunnel + Basic Auth (Prometheus)

Publiczny dostęp bez otwierania portów zapewnia Cloudflare Tunnel; Prometheus może być chroniony Basic Auth.

- Umieść poświadczenia tunelu w `ops/cloudflared/<TUNNEL-UUID>.json` i ustaw `TUNNEL-UUID` w `ops/cloudflared/config.yml`.
- (Opcjonalnie) Ustaw w `ops/prometheus/web.yml` sekcję `basic_auth_users` z własnym hashem bcrypt (przykład w pliku).
- Uruchom z override’ami:
  ```bash
  docker compose \
    -f docker-compose.yml \
    -f ops/compose.tunnel.yml \
    -f ops/compose.prometheus-auth.yml \
    up -d --build
  ```
- Skonfiguruj hosty w Zero Trust → Tunnels → Public Hostnames:
  `api.aionflow.net → http://api:8000`, `prometheus.aionflow.net → http://prometheus:9090`.

Zatrzymanie i sprzątanie:

```bash
make compose-down
```

## Endpoints (API)

Przykładowe wywołania:

```bash
curl -s http://localhost:8000/health

# Lista aktywów
curl -s http://localhost:8000/assets/

# Dodanie aktywa
curl -s -X POST http://localhost:8000/assets/ \
  -H 'content-type: application/json' \
  -d '{"symbol":"BTC","name":"Bitcoin"}'

# Ceny (okno 24h)
curl -s 'http://localhost:8000/prices?asset=BTC&window=24h'

# Podsumowanie 24h (szybsze do podglądu w UI)
curl -s 'http://localhost:8000/prices/summary?asset=BTC&window=24h'

# Alerty (ostatnie 20)
curl -s 'http://localhost:8000/alerts?asset=BTC&limit=20'
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

### Deploy z override'ami (Tunnel + Basic Auth)

- Skrypt respektuje zmienną `DEPLOY_OVERRIDES` i zawsze dołącza bazowy `docker-compose.yml`.
- Przykład (Cloudflare Tunnel + Prometheus Basic Auth):

```bash
DEPLOY_OVERRIDES="-f ops/compose.tunnel.yml -f ops/compose.prometheus-auth.yml" ./deploy.sh update
```

- Jeśli używasz wariantu tokenowego Cloudflare:

```bash
export CLOUDFLARE_TUNNEL_TOKEN='<twój_token_z_Zero_Trust>'
DEPLOY_OVERRIDES="-f ops/compose.tunnel.yml -f ops/compose.prometheus-auth.yml" ./deploy.sh update
```

- Weryfikacja:

```bash
curl -fsS http://localhost:8000/health
curl --http1.1 -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics        # 401
PASS='SuperBezpieczneHaslo123!' \
  && curl --http1.1 -u "admin:${PASS}" -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics  # 200
```

## Prometheus (przykładowe zapytania)

W UI Prometheusa (`/targets`, `/graph`):

- Ruch per endpoint: `sum by (path) (rate(api_requests_total[5m]))`
- p95 latencja: `histogram_quantile(0.95, sum by (le, path) (rate(api_request_duration_seconds_bucket[5m])))`
- Błędy HTTP per status: `sum by (status) (rate(api_errors_total[5m]))`
- Skuteczne pobrania cen: `sum by (symbol) (rate(fetch_price_success_total[5m]))`
- Alerty wygenerowane: `sum by (symbol) (rate(alerts_total[5m]))`

## Networking sanity

- Postgres/Redis nie mają wystawionych portów na hosta; dostęp tylko przez `docker compose exec`.
- API na `localhost:8000`, Prometheus (opcjonalnie) `localhost:9090`.
- UFW: otwórz tylko 8000 (i 9090 w zaufanej sieci), reszta zamknięta.

## Badge CI (opcjonalnie)

Dodaj w README (zastąp `ORG/REPO`):

```
[![CI](https://github.com/ORG/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/ORG/REPO/actions/workflows/ci.yml)
```

## CI (lint/test/build/scan)

Workflow CI uruchamia:
- Lint (ruff), typecheck (mypy), testy (pytest),
- Build obrazów (compose) oraz build tagowanych: `telemetry-board-api:latest`, `telemetry-board-worker:latest`,
- Skan bezpieczeństwa Trivy:
  - skan systemu plików repo (FS),
  - skan obrazów Docker (image) — nieblokujący (continue-on-error), poważne poziomy: CRITICAL,HIGH.

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
  - Backfill: tryb „portfolio” — automatyczny backfill jest wyłączony domyślnie (brak wpisów w harmonogramie).
    Zadania `backfill_prices`/`ensure_backfill` są dostępne do uruchomienia ręcznego (np. `celery call`), a w compose
    dane do wykresów 7d zapewnia `seed_mock_prices` (syntetyczne dane) przy `ENABLE_MOCK_SEED=true`.
  - Alerty (globalnie): `ALERT_WINDOW_MINUTES` (domyślnie: 60), `ALERT_THRESHOLD_PCT` (domyślnie: 5).
  - Retencja: `RETENTION_DAYS` — ile dni trzymać próbki (domyślnie: 30; ustaw `0`, aby wyłączyć sprzątanie) oraz
    `RETENTION_INTERVAL_SECONDS` — jak często uruchamiać sprzątanie (domyślnie: 86400 = 1 dzień).
    Zadanie `prune_old_prices` usuwa rekordy starsze niż `RETENTION_DAYS` — pomocne, by kontrolować zużycie dysku.

## Metryki

- API: `/metrics` (tekst Prometheusa). Zliczane są:
  - `api_requests_total{method,path}` — liczba żądań,
  - `api_request_duration_seconds{path}` — histogram czasu trwania,
  - `api_errors_total{method,path,status}` — liczba odpowiedzi o statusie >= 400.
- Worker: endpoint HTTP uruchamiany przez `prometheus_client.start_http_server` (domyślnie port 8001).

## Alerty per‑asset (opcjonalnie)

- Tabela `assets` posiada opcjonalne pola konfiguracyjne: `alert_pct` i `alert_window_min`.
- `compute_alerts` preferuje wartości per‑asset, a gdy są puste — korzysta z ENV: `ALERT_THRESHOLD_PCT`, `ALERT_WINDOW_MINUTES`.
- Aktualne API `/assets` nie wystawia jeszcze edycji tych pól (można ustawić z poziomu bazy; API zostanie rozszerzone w kolejnych iteracjach).

## Licencja

MIT
