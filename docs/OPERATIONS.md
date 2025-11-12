# Operacje: co zostało zrobione i co dalej

Poniżej znajdziesz podsumowanie wprowadzonych zmian oraz instrukcje „co dalej” – zarówno dla środowiska lokalnego (dev), jak i dla serwera (deploy/CD).

## 1) Co zostało zrobione

- API/Alerty: dopasowanie schematu odpowiedzi do modelu ORM
  - `app/api/alerts.py`: `AlertOut.triggered_at` → `datetime` (wcześniej `str`). FastAPI automatycznie serializuje do ISO 8601.
- Typowanie i stubs (mypy green w CI)
  - `worker/tasks/alerts.py`, `worker/tasks/prices.py`: adnotacje dla `self` w zadaniach Celery (bind=True).
  - `stubs/pytest/__init__.pyi`: dodano `MonkeyPatch.setattr` oraz `pytest.raises` (tylko dla mypy).
  - `stubs/requests/__init__.pyi`: minimalny stub (`Response`, `get`, `RequestException`) – unika potrzeby instalowania `types-requests` w CI.
  - `pyproject.toml`: dodano `httpx>=0.27` (wymagane przez `fastapi.testclient`).
- Docker/Compose: stabilne healthchecki bez dodatkowych pakietów i praca bez roota
  - `docker-compose.yml`:
    - API healthcheck używa Pythona (stdlib `urllib`) zamiast `curl`.
    - Worker healthcheck używa Pythona (socket `localhost:8001`).
    - `user: "65534:65534"` (nobody) dla `worker` i `beat` – koniec ostrzeżenia Celery o root.
    - `beat` uruchamiany z `-s /tmp/celerybeat-schedule` (zapisywalna ścieżka dla nie-root).
    - Ujednolicone `-A worker.worker_app:celery_app` (forma z dwukropkiem).
  - Dockerfile nie instalują dodatkowych pakietów systemowych (obrazy pozostają „slim”).
- Dokumentacja i narzędzia
  - `README.md`: doprecyzowano Alembic (`-c alembic.ini`), dodano skróty `deploy.sh` oraz sekcję o prostym CD.
  - `deploy.sh`: gotowy zestaw komend (`up/update/status/logs/down`).
  - `/.github/workflows/cd.yml`: prosty CD – na `push` do `main` (lub ręcznie) uruchamia `./deploy.sh update` na self‑hosted runnerze.

Gałąź robocza: `feature/deploy_polish` (scal do `main`, aby aktywować CD).

## 2) Co Ty masz zrobić – środowisko lokalne

- Aktualizacja zależności po zmianach:
  - `pip install -e .` (upewnia się, że `httpx` jest dostępny)
- Szybkie sanity:
  - `make lint && make typecheck && make test`
  - `uvicorn app.main:app --reload --port 8000`
  - Health: `curl -fsS http://localhost:8000/health`

## 3) Co Ty masz zrobić – serwer (deploy)

- Zaciągnij zmiany i zaktualizuj stack:
  - `git fetch && git checkout feature/deploy_polish && git pull`
  - `./deploy.sh update`
- Wymuś odtworzenie usług po zmianie użytkownika:
  - `docker compose up -d --force-recreate worker beat`
- Weryfikacje:
  - `./deploy.sh status` → `api` i `worker` powinny być `healthy`.
  - `docker compose exec worker id` → `uid=65534 gid=65534`.
  - Health: `curl -fsS http://localhost:8000/health`.
  - Metryki: `curl -s http://localhost:8000/metrics | head`.

## 4) Continuous Deployment (opcjonalne)

- Self‑hosted runner na serwerze (z labelami: `self-hosted`, `prod`).
- Po scaleniu do `main` workflow `Deploy` (/.github/workflows/cd.yml) uruchomi:
  - `./deploy.sh update` (build → up → migracje Alembica).
- Ręczny trigger dostępny z zakładki Actions (workflow_dispatch).

## 5) Rozwiązywanie problemów

- „Celery running as root” nadal widoczny:
  - Upewnij się, że serwer ma aktualny `docker-compose.yml` (z `user: "65534:65534"`).
  - `docker compose config | sed -n '1,200p'` – sprawdź efektywną konfigurację.
  - `docker compose up -d --force-recreate worker beat` – odtwórz kontenery.
  - `docker compose exec worker id` – potwierdź UID/GID.
- `health: starting` nie przechodzi w `healthy`:
  - API: `docker logs telemetry-board-api-1` – sprawdź start i `/health`.
  - `docker compose up -d --force-recreate api` – upewnij się, że healthcheck to wariant Python.
- Błędy Alembica:
  - Uruchom ręcznie wewnątrz kontenera: `docker compose run --rm api alembic -c alembic.ini upgrade head` i przejrzyj logi.
- Testy w CI: brak `httpx` → teraz dodane w `pyproject.toml`. Jeśli masz własne środowisko CI, pamiętaj o `pip install -e .`.

## 6) Rollback (minimalny)

- Powrót do poprzedniej wersji compose:
  - `git checkout <poprzedni_commit> -- docker-compose.yml`
  - `docker compose up -d`
- Lub pełen rollback repo: `git checkout <tag/commit>` i `./deploy.sh update`.

---
W razie pytań mogę dorzucić wariant CD z publikacją obrazów do GHCR i `docker compose pull`, jeśli chcesz oddzielić build od serwera docelowego.
Here’s a clear map of how your CI/CD works and how to use it.

Overview

CI builds confidence on every PR/push: lint, typecheck, tests, build.
CD auto-updates the server from main using your self-hosted runner.
Core files: .github/workflows/ci.yml, .github/workflows/cd.yml, deploy.sh, docker-compose.yml.
CI Pipeline

Workflow: .github/workflows/ci.yml
Steps:
Set up Python 3.11 and cache pip.
Install project deps: pip install -e . plus ruff mypy pytest.
Lint: ruff check .
Typecheck: mypy app worker tests
Tests: pytest -q with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and ANYIO_BACKEND=asyncio.
Build images: docker compose build --no-cache to validate Dockerfiles.
Purpose: catch style, typing, runtime regressions, and Docker build issues early.
Tests

Test client requires httpx (added in pyproject.toml) so imports succeed.
Plugins disabled via PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 for determinism.
AnyIO set to asyncio to keep FastAPI/Starlette stable in tests.
CD Pipeline

Workflow: .github/workflows/cd.yml
Triggers: push to main and manual “Run workflow”.
Runner: runs-on: [self-hosted, prod] (your server’s runner).
Deploy step: runs ./deploy.sh update which:
Builds images (docker compose build --no-cache)
Restarts services (docker compose up -d)
Applies DB migrations (alembic -c alembic.ini upgrade head)
Deploy Script

File: deploy.sh
Commands:
./deploy.sh up → start DBs → migrate → start app + worker + beat + Prometheus
./deploy.sh update → rebuild images → restart → migrate
status, logs, down, destroy for daily ops
Docker And Health

File: docker-compose.yml
API healthcheck: Python stdlib HTTP GET on /health (no curl needed).
Worker healthcheck: Python socket probe on port 8001.
Non-root processes: user: "65534:65534" for worker and beat.
Beat uses -s /tmp/celerybeat-schedule so it can write the schedule as non-root.
How To Trigger

CI:
Push/PR to any branch → .github/workflows/ci.yml runs automatically.
CD:
Merge/push to main → .github/workflows/cd.yml runs on the self-hosted runner.
Or run manually from GitHub Actions “Deploy” → “Run workflow”.
Troubleshooting

Worker still root: ensure the server has latest docker-compose.yml; then:
docker compose up -d --force-recreate worker beat
docker compose exec worker id → expect uid=65534
Health “starting”: force recreate API to refresh healthcheck:
docker compose up -d --force-recreate api
Alembic issues: run inside container for logs:
docker compose run --rm api alembic -c alembic.ini upgrade head
If you want, I can also add a GHCR-based CD (build images in CI, docker compose pull on server) for faster, lighter deploys.





## Konfiguracja backendu

- API
  - `ENABLE_METRICS_ENDPOINT` — odsłania `/metrics` (domyślnie wyłączone; włącz na wewnętrznych sieciach).
- Worker/Beat
  - `ENABLE_BEAT` — aktywuje harmonogram zadań (fetch/prune/alerts).
  - `ASSETS` — lista symboli do pobierania, np. `BTC,ETH`.
  - `FETCH_INTERVAL_SECONDS` — co ile sekund pobierać ceny (domyślnie 300).
  - Backfill: `ENABLE_BACKFILL_ON_START` — uruchom backfill przy starcie Beata (domyślnie: włączone) oraz
    `BACKFILL_HOURS` — rozmiar backfillu w godzinach (domyślnie 168 = 7 dni, aby UI 7d miało dane).
    `BACKFILL_CHECK_SECONDS` — interwał okresowego zadania `ensure_backfill` (domyślnie 600s),
    które nadrabia historię jeśli startowy backfill nie doszedł do skutku (np. kolejność startu usług).
  - `ALERT_WINDOW_MINUTES` — okno czasowe dla alertów (domyślnie 60).
  - `ALERT_THRESHOLD_PCT` — próg procentowy dla alertu (domyślnie 5).
  - Retencja danych:
    - `RETENTION_DAYS` — ile dni przechowywać dane cen (domyślnie 30). Ustaw `0`, aby wyłączyć czyszczenie.
    - `RETENTION_INTERVAL_SECONDS` — interwał uruchamiania czyszczenia (domyślnie 86400).
    - Zadanie `prune_old_prices` usuwa wiersze starsze niż `RETENTION_DAYS` — kontroluj dysk i rozmiar bazy.
