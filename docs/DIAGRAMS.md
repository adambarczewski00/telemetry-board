# Diagramy przepływu danych (Mermaid)

Poniżej zestaw kluczowych przepływów jako diagramy Mermaid. Można je podejrzeć w VS Code (rozszerzenia Mermaid) lub w przeglądarce (np. GitHub renderuje podstawowe diagramy).

## 1) Przepływ wysokopoziomowy (architektura runtime)

```mermaid
flowchart LR
  subgraph DockerNet[Docker network]
    API[API - FastAPI]
    Worker[Worker - Celery]
    Beat[Beat - scheduler]
    Redis[(Redis)]
    Postgres[(Postgres)]
    Prom[Prometheus]
  end

  Beat -->|schedule| Worker
  Worker -->|HTTP ceny| Provider[Provider cen]
  Worker -->|INSERT| Postgres
  API -->|SELECT/INSERT| Postgres
  API --- APIMetrics[metrics endpoint]
  Worker --- WorkerMetrics[metrics 8001]
  Prom -->|scrape| APIMetrics
  Prom -->|scrape| WorkerMetrics

  CF[Cloudflare Tunnel] --> API
  CF --> Prom
```

## 2) Zadanie pobierania cen (worker)

```mermaid
sequenceDiagram
  participant Beat as Beat (Celery)
  participant Worker as Worker
  participant Provider as Price Provider
  participant DB as Postgres
  participant M as Prometheus metrics

  Beat->>Worker: schedule fetch_price(symbols)
  Worker->>Provider: HTTP GET /prices
  Provider-->>Worker: 200 JSON (ceny)
  Worker->>DB: INSERT price_history
  Worker->>M: inc fetch_price_success_total
  Worker-->>Beat: ok
```

## 3) Obliczanie alertów (worker)

```mermaid
sequenceDiagram
  participant Beat as Beat (Celery)
  participant Worker as Worker
  participant DB as Postgres
  participant M as Prometheus metrics

  Beat->>Worker: schedule compute_alerts
  Worker->>DB: SELECT window cen
  Worker->>Worker: oblicz zmianę vs próg
  alt próg przekroczony
    Worker->>DB: INSERT alert
    Worker->>M: inc alerts_total
  else bez alertu
    Worker->>M: inc alert_checks_total
  end
```

## 4) Zapytanie API i metryki

```mermaid
sequenceDiagram
  participant C as Klient
  participant A as API
  participant DB as Postgres
  participant M as Prometheus metrics

  C->>A: GET /prices?asset=BTC
  A->>DB: SELECT najnowsze dane okna
  DB-->>A: wiersze
  A->>M: observe api_request_duration_seconds
  alt błąd
    A->>M: inc api_errors_total{status}
    A-->>C: 4xx/5xx
  else OK
    A-->>C: 200 JSON
  end
```

## 5) Tunel + Prometheus Basic Auth + scrape

```mermaid
flowchart TB
  User[Klient] -- https + BasicAuth --> CF[Cloudflare Tunnel]
  CF --> Prom[Prometheus]
  Prom -->|scrape metrics| API[API]
  Prom -->|scrape 8001| Worker[Worker]
```

---

Wskazówki operacyjne:
- Basic Auth wymaga uruchomienia z override `ops/compose.prometheus-auth.yml` (dodaje `--web.config.file` i montuje `ops/prometheus/web.yml`).
- Tunel: tryb tokenowy (`CLOUDFLARE_TUNNEL_TOKEN`) lub plik `ops/cloudflared/<UUID>.json` + `ops/cloudflared/config.yml`.
- Tryb bez publicznych portów: dołącz `ops/compose.tunnel.yml` (usuwa `ports:` z API/Prometheus).
