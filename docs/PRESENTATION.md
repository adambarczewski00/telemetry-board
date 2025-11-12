# Telemetry Board — dokument prezentacyjny (dla rekrutera)

Krótki dokument pokazujący wartość biznesową, decyzje techniczne oraz sposób uruchomienia i oceny projektu.

## Cel i wartość

- Cel: tablica telemetryczna do śledzenia cen krypto, alertów i kondycji systemu.
- Wartość: kompletne, spójne MVP łączące API + zadania okresowe + UI + metryki i gotowe do wdrożenia operacje.

## Najważniejsze funkcje

- API (FastAPI): zasoby aktywów i cen, podsumowania okien czasowych, zdrowie (`/health`).
- Zadania w tle (Celery): pobieranie cen, backfill historii, retencja danych, generowanie alertów.
- UI (Jinja2): overview, szczegóły aktywa, lista alertów.
- Metryki (Prometheus): API i worker (liczniki, histogramy), gotowe do scrape.
- Operacje: Docker Compose, `deploy.sh`, Prometheus, Cloudflare Tunnel (publiczny dostęp bez otwierania portów), Basic Auth dla Prometheusa.

## Architektura (skrót)

Diagramy przepływu (mermaid) są dostępne w `docs/DIAGRAMS.md`.

- API: `app/main.py`, endpointy w `app/api/*`, modele w `app/models/*`.
- Worker/Beat: `worker/worker_app.py`, zadania w `worker/tasks/*`.
- UI: `app/templates/*`, routing w `app/ui.py`.
- Metryki: rejestry w API i serwer w workerze.

## Stos i decyzje

- Python 3.11, FastAPI + Uvicorn, SQLAlchemy, Alembic.
- Celery + Redis (broker/result), Postgres (dane trwałe).
- Prometheus (monitoring) bezpośrednio z aplikacji i workera.
- Docker Compose – prosty, przewidywalny deploy bez zewnętrznych usług.
- Cloudflare Tunnel – publiczny dostęp do API/Prometheusa bez otwierania portów, prosty WAF/TLS.

## Operacje i bezpieczeństwo

- Compose: `docker-compose.yml` (baza), nadpisania w `ops/compose.tunnel.yml`, `ops/compose.prometheus-auth.yml`.
- Skrypt: `deploy.sh` (obsługuje `DEPLOY_OVERRIDES`).
- Prometheus Basic Auth: `ops/prometheus/web.yml` + override `ops/compose.prometheus-auth.yml`.
- Cloudflare Tunnel: `ops/cloudflared/config.yml` (plik JSON z poświadczeniami) lub tryb tokenowy (`CLOUDFLARE_TUNNEL_TOKEN`).
- Sekrety: `.gitignore` ignoruje pliki poświadczeń cloudflared.

## Jakość i testy

- Testy: scenariusze API, UI, worker, metryki, harmonogram – przechodzą w całości.
- Typowanie: mypy/stubs dla krytycznych miejsc (np. Celery bind=True, requests/httpx w testach).
- Lint/format: ruff/pre-commit.
- Ostrzeżenia (świadomie zostawione do refaktoru): FastAPI lifespan (zamiast on_event), TZ-aware datetimes, nowsze wywołanie TemplateResponse.

## Szybkie uruchomienie (lokalnie)

```bash
make compose-up
curl -fsS http://localhost:8000/health
# (opcjonalnie) Prometheus: http://localhost:9090/targets
```

## Wdrożenie z tunelem i Basic Auth

```bash
# (opcjonalnie) token Zero Trust
export CLOUDFLARE_TUNNEL_TOKEN='<token>'

# Prometheus Basic Auth – domyślny hash w repo; zalecana zmiana na własny
DEPLOY_OVERRIDES="-f ops/compose.tunnel.yml -f ops/compose.prometheus-auth.yml" \
  ./deploy.sh update

# Weryfikacja
curl -fsS http://localhost:8000/health
curl --http1.1 -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics        # 401
PASS='SuperBezpieczneHaslo123!' \
  && curl --http1.1 -u "admin:${PASS}" -s -o /dev/null -w "%{http_code}\n" http://localhost:9090/metrics  # 200
```

## Scenariusz demo (5 minut)

1) Health i zasoby
- `curl -s http://localhost:8000/health`
- `curl -s http://localhost:8000/assets/`

2) Dane cenowe i alerty
- `curl -s 'http://localhost:8000/prices?asset=BTC&window=24h' | head -n 1`
- `curl -s 'http://localhost:8000/alerts?asset=BTC&limit=5'`

3) UI
- Overview: `http://localhost:8000/ui/`
- Asset detail: `http://localhost:8000/ui/asset/BTC`
- Alerts: `http://localhost:8000/ui/alerts`

4) Metryki
- API: `curl -s http://localhost:8000/metrics | head`
- Prometheus (Basic Auth): `curl --http1.1 -u "admin:${PASS}" -s http://localhost:9090/api/v1/targets | jq .data.activeTargets[] .health`

## Na co zwrócić uwagę podczas code review

- `app/api/prices.py`, `worker/tasks/prices.py` – model danych i spójność API↔DB.
- `worker/tasks/alerts.py` – logika okien czasowych i progi.
- `app/main.py`, `tests/test_metrics.py` – eksponowanie i poprawność metryk.
- `deploy.sh`, `ops/*` – operacyjna gotowość (tunel, auth, brak portów publicznych).

## Roadmapa (krótko)

- Refaktor lifespanu FastAPI i TZ-aware datetimes.
- Panel admin (CRUD aktywów) i uwierzytelnianie UI.
- Eksport dashboardów (np. Grafana) i proste alerty Prometheusa.
- Build obrazu w CI i szybki pull na serwerze (GHCR).

---

Kontakt: autor projektu – patrz `README.md` i historia commitów.
