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
  - `README.md`: opisano metrykę `api_errors_total{method,path,status}` oraz skan obrazów Trivy w CI.
  - `deploy.sh`: gotowy zestaw komend (`up/update/status/logs/down`).
  - `/.github/workflows/cd.yml`: prosty CD – na `push` do `main` (lub ręcznie) uruchamia `./deploy.sh update` na self‑hosted runnerze.
  - Tryb portfolio: doprecyzowano, że automatyczny backfill jest wyłączony; dane dla 7d w demie zapewnia `seed_mock_prices`.

Gałąź robocza: `feature/deploy_polish` (scal do `main`, aby aktywować CD).

## 2) Co Ty masz zrobić – środowisko lokalne

- Aktualizacja zależności po zmianach:
  - `pip install -e .` (upewnia się, że `httpx` jest dostępny)
- Szybkie sanity:
  - `make lint && make typecheck && make test`
  - `uvicorn app.main:app --reload --port 8000`
  - Health: `curl -fsS http://localhost:8000/health`
  - Metryki (dev): `ENABLE_METRICS_ENDPOINT=true uvicorn app.main:app --port 8000` i `curl -s :8000/metrics | head`

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
  - Metryki: `curl -s http://localhost:8000/metrics | head` (powinno zawierać m.in. `api_requests_total`, `api_request_duration_seconds`, `api_errors_total`).

## Hosting przez Cloudflare Tunnel (bez reverse proxy, bez otwierania portów)

Cel: Uvicorn serwuje API w sieci Docker, Cloudflare zapewnia TLS/WAF i publiczny dostęp do hostów
`api.aionflow.net` i (opcjonalnie) `prometheus.aionflow.net` przez tunel — bez publikowania portów 8000/9090.

1) Utwórz tunel w Cloudflare Zero Trust
- Zero Trust → Tunnels → Create a tunnel → nadaj nazwę.
- Po utworzeniu pobierz `credentials.json` (dla danego Tunnel UUID) lub wykonaj polecenie instalacyjne loklanie i skopiuj plik.
- Zapisz plik jako `./ops/cloudflared/<TUNNEL-UUID>.json` (nie commituj sekretów do repo publicznego!).

2) W repo: konfiguracja i compose override
- Edytuj `ops/cloudflared/config.yml`: podmień `TUNNEL-UUID` na swój.
- Upewnij się, że DNS hosty odpowiadają domenie (tu: `aionflow.net`):
  - `api.aionflow.net` → service: `http://api:8000`
  - `prometheus.aionflow.net` → service: `http://prometheus:9090`
    - Jeśli trafiasz sporadycznie na 502 do backendu, możesz wymusić HTTP/1.1 do origin:
      w `ops/cloudflared/config.yml` dla tego hosta ustaw `originRequest.http2Origin: false` (już ustawione w repo).
- Uruchom z override dla tunelu:
  ```bash
  docker compose -f docker-compose.yml -f ops/compose.tunnel.yml up -d --build
  ```
  Override usuwa `ports:` z `api` i `prometheus`, dodaje serwis `cloudflared`.

3) Mapowanie hostów (Public Hostnames)
- W Cloudflare Zero Trust → Tunnels → twój tunel → Public Hostnames dodaj:
  - Hostname: `api.aionflow.net` → `http://api:8000`
  - Hostname: `prometheus.aionflow.net` → `http://prometheus:9090`
  (jeśli używasz pliku konfiguracyjnego, wpisy w `ingress:` już to odwzorowują)

4) Zabezpieczenie Prometheusa
- Zero Trust → Access → Applications: dodaj aplikację `prometheus.aionflow.net` i politykę (np. Email OTP, domena firmowa).
- Alternatywnie, nie wystawiaj Prometheusa publicznie i korzystaj z `docker compose exec`.

5) Weryfikacja
- `curl -s https://api.aionflow.net/health` → `{ "status": "ok" }`
- `https://api.aionflow.net/metrics` (jeśli `ENABLE_METRICS_ENDPOINT=true`) – włącz tylko, jeśli chcesz expose’ować metryki.
- `https://prometheus.aionflow.net/targets` (za Access, jeśli skonfigurowany).

### Prometheus z Basic Auth (alternatywa dla Cloudflare Access)

Aby zabezpieczyć Prometheusa hasłem bez Cloudflare Access, użyj wbudowanego mechanizmu Basic Auth.

- Skonfiguruj hasło w `ops/prometheus/web.yml`:
  - Wygeneruj hash bcrypt (np. `htpasswd -nBC 12 "" | tr -d ':\n'`).
  - Ustaw użytkownika i hash w sekcji `basic_auth_users` (przykład jest zakomentowany w pliku).
- Dołącz override `ops/compose.prometheus-auth.yml`, który montuje `web.yml` i uruchamia Prometheusa z
  `--web.config.file=/etc/prometheus/web.yml`.

Uruchomienie tunelu + Basic Auth:

```bash
docker compose \
  -f docker-compose.yml \
  -f ops/compose.tunnel.yml \
  -f ops/compose.prometheus-auth.yml \
  up -d --build
```

Szybkie testy:

```bash
# Bez hasła (401)
curl --http1.1 -s -o /dev/null -w "no-auth: %{http_code}\n" https://prometheus.aionflow.net/metrics

# Z hasłem (200) — zastąp własnym hasłem
PASS='SuperBezpieczneHaslo123!'
curl --http1.1 -u "admin:${PASS}" -s -o /dev/null -w "auth: %{http_code}\n" https://prometheus.aionflow.net/metrics

# Podgląd metryk
curl --http1.1 -u "admin:${PASS}" -s https://prometheus.aionflow.net/metrics | head -n 5
```

Oczekiwany wynik:

```
no-auth: 401
auth: 200
# HELP go_gc_cycles_automatic_gc_cycles_total ...
```

Weryfikacja stanu tunelu:

```bash
docker logs telemetry-board-cloudflared-1 --tail=50 | egrep -i 'tunnel|connect|error'
```

Przykładowe zdrowe logi:

```
INF Registered tunnel connection connIndex=0 location=fra10 protocol=quic
INF Updated to new configuration config="{\"ingress\":[...]}" version=2
```

### Wariant tokenowy (bez pliku JSON)

Zamiast `credentials-file` możesz użyć tokenu z Zero Trust:

```bash
export CLOUDFLARE_TUNNEL_TOKEN='<twój_token_z_Zero_Trust>'
docker compose -f docker-compose.yml -f ops/compose.tunnel.yml up -d --force-recreate cloudflared
```

Skrypt `deploy.sh` wspiera override'y przez `DEPLOY_OVERRIDES` i zawsze dołącza bazę `docker-compose.yml`:

```bash
DEPLOY_OVERRIDES="-f ops/compose.tunnel.yml -f ops/compose.prometheus-auth.yml" ./deploy.sh update
```

Weryfikacja końcowa:

```bash
curl -fsS http://localhost:8000/health                                         # 200
curl --http1.1 -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics        # 401
PASS='SuperBezpieczneHaslo123!' \
  && curl --http1.1 -u "admin:${PASS}" -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics   # 200
curl -fsS https://api.aionflow.net/health                                      # 200 przez tunel
curl --http1.1 -u "admin:${PASS}" -s -o /dev/null -w "%{http_code}\n" https://prometheus.aionflow.net/metrics  # 200 przez tunel
```

Uwagi
- Postgres/Redis nadal bez `ports:` — pozostają prywatne (tak jak w podstawowym compose).
- W środowiskach produkcyjnych rozważ `ENABLE_METRICS_ENDPOINT=false` i obserwację API przez wewnętrznego Prometheusa.
- `cloudflared` w compose używa pliku `ops/cloudflared/config.yml` i wymaga obecności pliku poświadczeń `<UUID>.json` w tym samym katalogu.

### Przydatne komendy operacyjne

- PSQL w kontenerze Postgresa:
  - `docker compose exec -e PGPASSWORD=app postgres psql -U app -d app`
- Redis CLI w kontenerze:
  - `docker compose exec redis redis-cli ping`
- Ręczne zadanie Celery (seed/backfill):
  - `docker compose exec worker celery -A worker.worker_app:celery_app call seed_mock_prices --args='["BTC", 168, 300]'`
  - `docker compose exec worker celery -A worker.worker_app:celery_app call backfill_prices --args='["BTC", 168]'`
- Podgląd logów:
  - `./deploy.sh logs`

### Kopie zapasowe (proste)

- Dump bazy (w kontenerze postgres):
  - `docker compose exec -e PGPASSWORD=app postgres pg_dump -U app -d app -Fc -f /tmp/app.dump`
  - `docker compose cp postgres:/tmp/app.dump ./app.dump`
- Przywrócenie (uwaga na downtime):
  - `docker compose cp ./app.dump postgres:/tmp/app.dump`
  - `docker compose exec -e PGPASSWORD=app postgres pg_restore -U app -d app -c /tmp/app.dump`

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
