
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
   — ✔️ (README/CODEOWNERS/CONTRIBUTING/LICENSE/.gitignore oraz dodane .editorconfig)

2. **Makefile** (pod Ubuntu/Docker CLI): — ✔️

```Makefile
.PHONY: bootstrap-dev lint format typecheck test build compose-up compose-down

bootstrap-dev:
\t@echo "Host bootstrap handled outside (apt + docker)."

lint:
\truff check .

format:
\truff format .

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

3. **pyproject.toml** — ✔️

4. **Dockerfile.api / Dockerfile.worker** (multi-stage na `python:3.11-slim`): — ✔️

   * Dodaj build stage (`builder`) z `pip wheel` i final stage z minimalnym runtime.
   * Na Ubuntu host nie ma znaczenia — ważne by obrazy były „slim”.

5. **docker-compose.yml** — uzupełnij o **Prometheus** i zdrowie serwisów: — ✔️ (pliki i healthchecki są)

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

6. **prometheus.yml** (w repo w `ops/prometheus.yml`): — ✔️

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

7. **CI (GitHub Actions)** — `ubuntu-latest`, Python 3.11, ruff/mypy/pytest, build obrazów, Trivy z `exit-code: 0`. — ✔️ (dodano .github/workflows/ci.yml)

8. **README** — sekcja „Uruchomienie na Ubuntu” z komendami z Kroku 0 i `make compose-up`. — ✔️ (dodano szybki start, dev, konfigurację)

**DoD F0 (Ubuntu):**

* `docker compose up -d --build` uruchamia **api/worker/redis/postgres/prometheus**.
* `/health` zwraca `ok` (sprawdzone: `curl localhost:8000/health`).
* Prometheus widzi `api` i `worker` (Targets = UP) po sieci dockerowej.
* CI zielone na `ubuntu-latest`.

---

### F1 — Szkielet API + modele DB + metryki (2–3 h)

1. **Modele SQLAlchemy**: `assets`, `price_history`, `alerts` + migracje (alembic). — ✔️ (modele + alembic init + baza migracja)
   — *Ubuntu note*: brak różnic.

2. **FastAPI**: `/health`, `/metrics`, `/assets` (GET/POST), `/prices`, `/alerts`.
   — ✔️ `/health`, ✔️ `/metrics`, ✔️ `/assets` GET/POST, ✔️ `/prices` (MVP), ✔️ `/alerts` (MVP).
   — *Metryki*: `prometheus_client` + middleware (✔️ licznik i histogram).
   — *Ważne*: Nie wystawiaj `/metrics` publicznie poza siecią compose (lokalnie wystawione przez port 8000 dla demo).

3. **Konfiguracja** przez zmienne środowiskowe (jak w compose). — częściowo (app: `ENABLE_METRICS_ENDPOINT`, `DATABASE_URL` dla DB; worker: `REDIS_URL`, `ENABLE_WORKER_METRICS`, `WORKER_METRICS_PORT`)

**DoD F1 (Ubuntu):**

* `/assets` GET/POST działa. ✔️
* `/prices` zwraca pustą serię lub dane testowe. ✔️ (MVP; walidacja istnienia assetu)
* `/metrics` działa; Prometheus target `api` = UP.

---

### F2 — Worker + pierwszy realny fetch (2–3 h)

1. **Celery app** (Redis broker/backend) — zarejestruj zadania. — ✔️ (bazowy worker + `ping` + rejestracja tasks)
2. **Zadania periodyczne**: `fetch_price(asset)` co 1–5 min → zapis do `price_history` (UPSERT po `(asset_id, ts)`). — ✔️ (task + harmonogram przez Celery Beat, env: ASSETS/FETCH_INTERVAL_SECONDS)
3. **Źródło**: CoinGecko/alternatywa (requests + backoff). — ✔️ (MVP: CoinGecko simple/price; testy z mockiem)
4. **Metryki workera**: `prometheus_client.start_http_server(8001)` (wewnątrz kontenera `worker`). — ✔️ (liczniki + histogram dla taska)

**DoD F2 (Ubuntu):**

* Worker zapisuje realne ceny (min. `BTC`) do Postgresa. ✔️ (w testach oraz realnie przy dostępnej sieci)
* Prometheus scrapuje `worker` i widać wzrost liczników. ✔️ (endpoint działa; liczniki dodane)
* Beat uruchamia `fetch_price` cyklicznie (compose: usługa `beat`). ✔️

---

## Dzień 2 — Alerty + polishing + portfolio

### F3 — Alerty procentowe + endpointy (2 h)

* Reguła N% w M min, parametry globalne/per-asset. — ✔️ (ENV: ALERT_WINDOW_MINUTES, ALERT_THRESHOLD_PCT)
* Task okresowy liczy `change_pct` i zapisuje do `alerts`. — ✔️ (`compute_alerts` + beat)
* `/alerts?asset=BTC&limit=20`. — ✔️ (MVP z F1)
* Logi JSON ze szczegółami alertu. — TODO (opcjonalnie)
* Metryki: `alerts_total`, `alert_compute_seconds`. — ✔️

**DoD F3 (Ubuntu):**

* Pojawia się alert po spełnieniu warunku. ✔️ (testy `test_alerts_compute.py`)

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

## Strategia gałęzi i commitów (plan)

- Główne zasady:
  - Małe, izolowane PR-y, każdy zielony na CI przed merge.
  - Konwencje commitów: `feat:`, `fix:`, `chore:`, `test:` (+ prefiks modułu, np. `api`, `db`).
  - Branch per feature; rebase na `main` przed PR.

- Gałęzie F1:
  - `feature/f1-models-db` — modele SQLAlchemy + konfiguracja DB + alembic init.
  - `feature/f1-assets-endpoints` — `/assets` GET/POST + schematy Pydantic.
  - `feature/f1-prices-alerts` — `/prices`, `/alerts` (MVP, bez workera).

- Przybliżone commity (przykłady):
  - `feat(db): add SQLAlchemy models (assets, price_history, alerts)`
  - `feat(db): add settings + session factory`
  - `chore(alembic): init and base revision`
  - `feat(api): add /assets GET/POST + schemas`
  - `test(api): add /assets tests (create/list/validation)`
  - `feat(api): add /prices MVP (empty or mock)`
  - `feat(api): add /alerts MVP (empty or mock)`
  - `test(api): add /prices and /alerts tests`

- PR-y:
  - 1 PR per gałąź, opis zmian + kroki weryfikacji: `ruff`, `mypy`, `pytest`, `docker compose build`.

## Plan testów jednostkowych (F1)

- testy istniejące: `tests/test_health.py`, `tests/test_metrics.py` — pozostają.
- nowe pliki:
  - `tests/test_assets.py`
    - `test_get_assets_empty`
    - `test_create_asset_valid`
    - `test_create_asset_duplicate`
    - `test_create_asset_validation`
  - `tests/test_prices.py`
    - `test_get_prices_empty`
    - `test_get_prices_invalid_asset`
    - `test_get_prices_window_param`
  - `tests/test_alerts.py`
    - `test_get_alerts_empty`
    - `test_get_alerts_invalid_asset`

- uwagi:
  - FastAPI `TestClient`, baza: in-memory/tymczasowa z izolacją na test (fixture).
  - Bez zewnętrznych serwisów; worker nieużywany w F1.


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

---

## Stan prac i kontekst (do kontynuacji)

- Podsumowanie statusu:
  - F0 ✔️, F1 ✔️, F2 ✔️ (wraz z Beat), F3 ✔️ (bez opcjonalnych logów JSON).
  - Testy pokrywają: health/metrics, assets, prices/alerts (MVP), worker fetch (+ błędy), beat schedule, compute_alerts oraz integrację API po fetchu.

- Otwarte gałęzie/PR (do review/merge):
  - feature/f1-assets-endpoints → PR draft (assets GET/POST + testy)
  - feature/f1-prices-alerts → PR draft (prices/alerts MVP + testy)
  - feature/f2-worker-fetch → PR draft (fetch_price + metryki + test)
  - feature/f2-beat-schedule → PR draft (Beat + harmonogram + test + compose)
  - feature/tests-worker-and-api → PR draft (testy błędów workera i integracja API)
  - feature/f3-alerts-compute → PR draft (compute_alerts + metryki + testy, rozszerzony Beat)

- Najbliższe kroki (F4 — UI, najprostszy stack):
  - Stack: FastAPI Templates (Jinja2) + htmx (opcjonalnie) + Chart.js (CDN) + Pico.css (CDN). Bez Node/Vite i bez kompilacji.
  - Routing UI: dodać `app/ui.py` (APIRouter) z trasami: `/ui` (overview), `/ui/assets/{symbol}` (asset detail), `/ui/alerts` (lista/dodawanie alertów).
  - Szablony: `app/templates/{base.html,overview.html,asset.html,alerts.html}`; fragmenty pod htmx dla tabel/list.
  - Statyczne pliki: katalog `app/static/` i montaż `StaticFiles` pod `/static`; biblioteki z CDN (Chart.js, Pico.css, htmx).
  - Integracja: w `app/main.py` dodać montaż statyków oraz `include_router(ui_router)` pod prefiksem `/ui`.
  - Interakcja: proste odpytywanie (`fetch`/htmx) co 10–15 s do `/prices?asset=...` i `/alerts?asset=...` + render wykresu w Chart.js.
  - Akceptacja: strona `/ui` pokazuje listę aktywów z ostatnią ceną i 24h zmianą; `/ui/assets/BTC` renderuje wykres + ostatnie alerty; `/ui/alerts` pozwala dodać alert progu dla aktywa.
  - (Opcjonalnie, F5) SSE/WebSocket do live‑update; na start polling wystarczy.
  - Dokumentacja: krótka sekcja w README „UI” (jak wejść, co działa) + 1–2 screenshoty.

— Koniec kontekstu: tu zakończono pracę; kontynuuj od listy „Najbliższe kroki (F4)”.

## F4 — Backend finish (stability first)

Cel: minimalny i stabilny backend, gotowy do działania 24/7, UI dokończymy na końcu.

- API
  - /prices honoruje `window` (minuty, h, d) — ✔️ zrobione
  - /prices/summary (points, first, last, min, max, avg) — ✔️ zrobione
  - /alerts (GET) — ✔️ jest, dopracować limity i walidację
  - (opcjonalnie) POST/DELETE /alerts dla user‑defined alertów — odłożyć
- Worker
  - fetch_price: timeout 10s — ✔️; mapowanie BTC/ETH — ✔️; dodać prosty backoff przy HTTP 429/5xx (exponential sleep) — pending
  - compute_alerts: okno/prog z ENV — ✔️; metryki — ✔️
  - Retencja: dodać okresowe czyszczenie starych próbek (np. >30d, ENV RETENTION_DAYS) — pending
  - Indeksy: upewnić się o (asset_id, ts) i uniq (jest w modelu) — dodać migrację Alembic — pending
- Operacyjność
  - Prometheus: metryki API/worker — ✔️
  - Konfiguracja przez ENV: ASSETS, FETCH_INTERVAL_SECONDS, ALERT_WINDOW_MINUTES, ALERT_THRESHOLD_PCT, RETENTION_DAYS (nowe) — ✔️ udokumentowane
  - Skromne limity/guardy: cap `limit` w /alerts (jest), walidacja `window` — ✔️

Plan implementacji (backend)
1) Dodać `GET /prices/summary` i `window` w /prices — ✔️
2) Retention task (Celery beat): usuń PriceHistory starsze niż N dni (ENV RETENTION_DAYS, domyślnie 30) — pending
3) Prosty backoff w fetch_price (na 429/5xx): retry po 1s, 2s, 4s (max 3 próby) — pending
4) Alembic migration: indeks po (asset_id, ts), walidacja uniq (jeśli brak w migracjach) — pending
5) README/OPERATIONS: sekcja „Konfiguracja backendu” — ✔️ dodana

Plan testów (backend)
- API
  - test_prices_window_filter — ✔️ tests/test_prices.py
  - test_prices_invalid_window — ✔️ tests/test_prices.py
  - test_prices_summary_empty i stats — ✔️ tests/test_prices_summary.py
  - test_alerts_limit_order — ✔️ (już istnieje)
- Worker
  - test_worker_fetch_success — ✔️ tests/test_worker_fetch.py
  - test_worker_fetch_backoff_on_429/5xx — dodać (monkeypatch requests.get)
  - test_alerts_compute_env_window_threshold — ✔️ (już istnieje)
  - test_alert_metrics_increment — ✔️ tests/test_alerts_metrics.py
  - test_beat_schedule_assets_interval — ✔️ (istnieje schedule test)
- Retencja
  - test_retention_task_removes_old_rows — ✔️ tests/test_retention.py

Akceptacja (backend)
- Po 2–5 minutach od startu: `/prices?asset=BTC&window=24h` zwraca punkty; `/prices/summary` zwraca statystyki.
- Alerty generują się w oknie i progu z ENV, `/alerts?asset=BTC&limit=20` zwraca co najmniej jeden alert przy większym ruchu.
- Metryki API/worker są dostępne, Prometheus ma targety UP.
- Retencja usuwa stare dane zgodnie z ENV (jeśli ustawione), brak wycieków połączeń.

Na końcu (F5) dopracujemy UI na bazie stabilnego backendu.

Here’s a practical roadmap to move the app forward — especially a simple, useful UI.

Product Roadmap

Core features
Alerts management: list/create/delete alerts; configurable thresholds per asset.
Price history charts: 1h/24h/7d windows; min/max/avg.
Asset catalog: add/remove assets; names/aliases; validation.
Realtime
Live price ticks and alerts via WebSocket or Server‑Sent Events.
Background aggregation for faster charts (rolling buckets).
Operability
Auth (API key or basic OAuth proxy) for write endpoints.
Rate limits for public endpoints; CORS for UI.
Retention policy (cleanup old PriceHistory), configurable via env.
UI MVP (served by the API)

Pages
Overview: table of assets with last price, 24h change, last alert badge.
Asset Detail: line chart of price vs time, recent alerts list.
Alerts: list and simple form to add threshold alert per asset.
Settings: manage tracked assets, thresholds defaults.
Tech (simplest, no build)
Server‑rendered templates (Jinja2) + htmx for partial updates (optional).
Chart.js via CDN for charts; Pico.css via CDN for styling.
Served by FastAPI StaticFiles under `/static`. No Node, no bundler.
Data
GET /prices/?asset=BTC&window=24h → list of {ts, price}.
GET /alerts/?asset=BTC&limit=50.
POST /alerts/ → create per‑asset threshold.
Optional: GET /assets/ for dropdowns.
Realtime (phase 2)
Start with polling every 10–15s. Optional: SSE `/sse` or WebSocket `/ws` later.
API Enhancements

Prices aggregation
GET /prices/summary?asset=BTC&window=24h → {min,max,avg,first,last,points}.
Add DB index on (asset_id, ts); optional downsampling job.
Alerts CRUD
POST /alerts/ body: {asset, window_minutes, threshold_pct, direction}.
DELETE /alerts/{id}; GET /alerts?asset=....
Config
GET/PUT /config/alerts-defaults to adjust _settings() centrally.
Validation/limits
Query param validation, sane limit defaults; 400 on misuse.
Security/Perf

Auth
Simple API token env (API_TOKEN) → FastAPI dependency for writes.
Rate limiting
slowapi (Redis) for POSTs; safe defaults for GETs.
CORS
Allow UI origin; configurable via ALLOWED_ORIGINS.
Grafana Option (fastest “UI”)

Add Grafana in compose; create dashboards for:
Price charts per asset (pull from API/Prometheus exporters).
Alerts count, worker timings, API latencies.
This complements (doesn’t replace) a thin app UI.
Proposed Implementation Plan (minimal stack)

Add price summary endpoint and basic alerts CRUD (reuse existing GET, add POST/DELETE if needed).
Add UI router + templates; serve static and wire CDN libraries.
Implement Overview/Asset/Alerts pages with polling fetch/htmx and Chart.js render.
Optional later: SSE/WebSocket push from Celery for live updates.
Document UI usage; add a couple of UI smoke tests (200 responses) and update README.

## F5 — UI (minimal, bez SPA) — plan szczegółowy

Cele:
- Bez build stepu, zero SPA. Tylko Jinja2 + Pico.css + Chart.js (CDN) + prosty JS (fetch + setInterval).
- Widoki: Overview (lista aktywów), Asset detail (wykres + alerty), Alerts (lista per asset).

Widoki i funkcjonalności:
- Overview (`app/templates/overview.html`)
  - Lista aktywów z `/assets` (symbol, name).
  - Ostatnia cena i zmiana 24h wyliczana klientem z `/prices?asset=SYM&window=24h`.
  - Link „Open” do `/ui/assets/{symbol}`.
  - Polling co 15 s; stany: „No assets yet”, „n/a” przy błędzie.
- Asset detail (`app/templates/asset.html`)
  - Wykres (Chart.js) z `/prices?asset=SYM&window=24h` (labels: czas, data: price).
  - Tabela alertów z `/alerts?asset=SYM&limit=20` (Time, Window, Change %).
  - Polling co 15 s; stan pusty gdy brak cen/alertów.
- Alerts (`app/templates/alerts.html`)
  - Select z listą aktywów `/assets`, tabela alertów `/alerts?asset=...&limit=50`.
  - Auto‑odświeżanie co 15 s i przy zmianie selecta; stan pusty gdy brak danych.

Zależności (bez buildu):
- CSS: Pico.css z CDN (już dołączone w `app/templates/base.html`).
- JS: Chart.js z CDN (już dołączone), opcjonalnie htmx (już dołączone, użycie minimalne/na później).

Integracje API (bez zmian backendu):
- `/assets`, `/prices?asset=SYM&window=24h`, `/alerts?asset=SYM&limit=N`.
- Opcjonalnie w przyszłości: `/prices/summary` dla skrótów (nie wymagane teraz).

UX i dostępność:
- Stany ładowania: placeholdery/puste komunikaty (zrobione w widokach).
- Błędy: fallback „n/a” lub puste wiersze; brak alertów → komunikat.
- Format liczb: `toFixed(2)`; zmiany 24h z prefiksem `+`/`-`.

Akceptacja (UI):
- Overview wyświetla listę aktywów, ostatnią cenę i 24h zmianę po dodaniu min. jednego aktywa.
- Asset detail renderuje wykres (gdy są ceny) i listę alertów.
- Alerts pokazuje alerty dla wybranego aktywa; przełączanie działa; auto‑refresh co 15 s działa.
- Brak dodatkowych buildów/serwerów frontu; wszystko serwowane przez FastAPI.

Plan wykonania:
1) Dopracowanie tabel/kolorowania zmian na Overview (opcjonalnie: kolor zielony/czerwony). [1–2h]
2) Asset detail: drobne poprawki osi/ticków i komunikatów; w razie potrzeby odchudzenie datasetu. [1h]
3) Alerts: poprawa UX selecta (zachowanie wyboru po refreshu) i sortowanie po stronie API (już desc). [1h]

Testy/Sprawdzenie (ręczne, bez E2E tooli):
- Status HTTP 200 dla `/ui`, `/ui/assets/BTC`, `/ui/alerts` przez `TestClient` (prosty smoke test).
- Manual: dodać aktywo przez `/assets`, zasymulować wpisy cen, sprawdzić odświeżanie tabel/wykresu.

Możliwe rozszerzenia (po MVP):
- Zamiast pollingu: SSE/WebSocket tylko dla wykresu.
- Uproszczone KPI na Overview z `/prices/summary`.
- Dodanie formularza tworzenia alertów użytkownika (POST/DELETE /alerts — poza MVP).
