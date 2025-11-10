
---

telemetry-board/
├─ app/            # FastAPI
├─ worker/         # Celery
├─ tests/
├─ ops/            # prometheus.yml, CI itp.
├─ .gitignore
├─ .editorconfig
├─ pyproject.toml  # zależności + configi lintów
├─ .pre-commit-config.yaml
├─ Makefile


## Dzień 1 — Fundamenty + pierwszy przepływ

### F0 — Repo + CI + Compose (2–3 h)

1. **Repo**: jak opisałeś (README/LICENCE/CONTRIBUTING/CODEOWNERS/.editorconfig/.gitignore).
   — *Ubuntu note*: nic specjalnego.

2. **Makefile** (pod Ubuntu/Docker CLI):

```Makefile
.PHONY: bootstrap-dev lint format typecheck test build compose-up compose-down

bootstrap-dev:
\t@echo "Host bootstrap handled outside (apt + docker)."

lint:
\truff check .

format:
\tblack .

typecheck:
\tmypy .

test:
\tpytest -q

build:
\tdocker compose build --no-cache

compose-up:
\tdocker compose up -d --build

compose-down:
\tdocker compose down -v
```

3. **pyproject.toml** — masz ✔️.

4. **Dockerfile.api / Dockerfile.worker** (multi-stage na `python:3.11-slim`):

   * Dodaj build stage (`builder`) z `pip wheel` i final stage z minimalnym runtime.
   * Na Ubuntu host nie ma znaczenia — ważne by obrazy były „slim”.

5. **docker-compose.yml** — uzupełnij o **Prometheus** i zdrowie serwisów:

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      - DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/app
      - REDIS_URL=redis://redis:6379/0
      - PROMETHEUS_MULTIPROC_DIR=/tmp/metrics
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 2s
      retries: 5
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: .
    dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql+psycopg://app:app@postgres:5432/app
      - REDIS_URL=redis://redis:6379/0
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'ss -ltn | grep -q :8001'"]
      interval: 10s
      timeout: 2s
      retries: 5
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=app
      - POSTGRES_PASSWORD=app
      - POSTGRES_DB=app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 10s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 10

  prometheus:
    image: prom/prometheus:v2.55.0
    volumes:
      - ./ops/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
    ports:
      - "9090:9090"
    depends_on:
      - api
      - worker

volumes:
  pgdata:
  redisdata:
```

6. **prometheus.yml** (w repo w `ops/prometheus.yml`):

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "api"
    static_configs:
      - targets: ["api:8000"]

  - job_name: "worker"
    static_configs:
      - targets: ["worker:8001"]
```

7. **CI (GitHub Actions)** — `ubuntu-latest`, Python 3.11, ruff/black/mypy/pytest, build obrazów, Trivy z `exit-code: 0`.

8. **README** — sekcja „Uruchomienie na Ubuntu” z komendami z Kroku 0 i `make compose-up`.

**DoD F0 (Ubuntu):**

* `docker compose up -d --build` uruchamia **api/worker/redis/postgres/prometheus**.
* `/health` zwraca `ok` (sprawdzone: `curl localhost:8000/health`).
* Prometheus widzi `api` i `worker` (Targets = UP) po sieci dockerowej.
* CI zielone na `ubuntu-latest`.

---

### F1 — Szkielet API + modele DB + metryki (2–3 h)

1. **Modele SQLAlchemy**: `assets`, `price_history`, `alerts` + migracje (alembic).
   — *Ubuntu note*: brak różnic.

2. **FastAPI**: `/health`, `/metrics`, `/assets` (GET/POST), `/prices`, `/alerts`.
   — *Metryki*: `prometheus_client`. Dla Uvicorn/ASGI możesz dodać własny middleware (licznik requestów, histogram latencji, licznik błędów).
   — *Ważne*: Nie wystawiaj `/metrics` publicznie poza siecią compose (i tak jest tylko wewnątrz).

3. **Konfiguracja** przez zmienne środowiskowe (jak w compose).

**DoD F1 (Ubuntu):**

* `/assets` GET/POST działa.
* `/prices` zwraca pustą serię lub dane testowe.
* `/metrics` działa; Prometheus target `api` = UP.

---

### F2 — Worker + pierwszy realny fetch (2–3 h)

1. **Celery app** (Redis broker/backend) — zarejestruj zadania.
2. **Zadania periodyczne**: `fetch_price(asset)` co 1–5 min → zapis do `price_history` (UPSERT po `(asset_id, ts)`).
3. **Źródło**: CoinGecko/alternatywa (requests + backoff).
4. **Metryki workera**: `prometheus_client.start_http_server(8001)` (wewnątrz kontenera `worker`).

**DoD F2 (Ubuntu):**

* Worker zapisuje realne ceny (min. `BTC`) do Postgresa.
* Prometheus scrapuje `worker` i widać wzrost liczników.

---

## Dzień 2 — Alerty + polishing + portfolio

### F3 — Alerty procentowe + endpointy (2 h)

* Reguła N% w M min, parametry globalne/per-asset.
* Task okresowy liczy `change_pct` i zapisuje do `alerts`.
* `/alerts?asset=BTC&limit=20`.
* Logi JSON ze szczegółami alertu.
* Metryki: `alerts_total`, `alert_compute_seconds`.

**DoD F3 (Ubuntu):**

* Pojawia się alert po spełnieniu warunku.

### F4 — Testy + dokumentacja + „HR polish” (2–3 h)

* **Testy**: unit + integracja (worker→DB→API).
* **README (Ubuntu)**: pełne uruchomienie, Mermaid, Prometheus, SLO, Security/Networking.
* **Screenshots/**: `docker compose ps`, log workera, `curl /prices`, `curl /alerts`, Prometheus Targets.
* **CI badge** + tag `v0.1.0`.

**DoD F4 (Ubuntu):**

* Testy i CI zielone.
* Prometheus scrapuje oba endpointy.

---

## Wzorce JSON (MVP) — bez zmian

* `GET /assets`
* `POST /assets`
* `GET /prices?asset=BTC&window=24h`
* `GET /alerts?asset=BTC&limit=20`

---

## Minimalne DDL (SQL) — bez zmian

* `assets`, `price_history`, `alerts` (+ alembic).

---

## Celery — rate-limit/backoff — bez zmian (implementacja po MVP)

---

## Checklist „anty-potknięcia” (Ubuntu)

* `docker info` **bez** `"iptables": false`.
* `postgres` i `redis` **bez** `ports:` (only internal).
* `api` dostępne lokalnie: `curl http://localhost:8000/health`.
* Dodany `BTC` (i np. `ETH`) przez `/assets`.
* Po 2–5 min pojawiają się rekordy w `price_history`.
* `/prices?asset=BTC&window=24h` zwraca serię.
* Co najmniej 1 alert dla testu.
* Prometheus Targets (`api`, `worker`) = **UP**.
* CI badge = green, tag `v0.1.0`.
* **UFW**: otwarte tylko 8000 (API) i 9090 (Prometheus – opcjonalnie).
* **Grupa docker**: użytkownik dodany (`id -nG | grep docker`).
* **SELinux/AppArmor**: na Ubuntu standardowo OK; jeśli restrykcje, sprawdź `docker info`/`dmesg`.

---

## Szybki start (Ubuntu)

```bash
git clone <repo> telemetry-board
cd telemetry-board

# pierwszy raz po instalacji dockera:
# (upewnij się, że jesteś w grupie docker i zaloguj się ponownie)

make compose-up
curl http://localhost:8000/health      # => ok
# otwórz http://localhost:9090/targets  # powinno być UP dla api i worker
```
