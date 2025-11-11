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
