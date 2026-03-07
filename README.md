# otel-slo-guard-demo

Failure-injected microservices instrumented with OpenTelemetry, SLO error budgets, and burn-rate alerting.
```
service_a → service_b → OTel Collector → Jaeger
                      ↘ Prometheus → Alertmanager → webhook
                                   → Grafana dashboards
```

## Quickstart
```bash
git clone https://github.com/<you>/otel-slo-guard-demo
cd otel-slo-guard-demo
docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml up -d --build
```

First run takes ~2 min to build. Then open:
- Grafana: http://localhost:3000 (admin/admin)
- Jaeger: http://localhost:16686
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093

## Ports

| Service             | Port  | Purpose                          |
|---------------------|-------|----------------------------------|
| service_a           | 8001  | Gateway: /healthz /work /metrics |
| service_b           | 8002  | Dependency: /healthz /compute /metrics /admin/failmode |
| Jaeger UI           | 16686 | Distributed trace explorer       |
| Prometheus          | 9090  | Metrics + alert rules            |
| Alertmanager        | 9093  | Alert routing                    |
| Grafana             | 3000  | SLO dashboards                   |
| Webhook receiver    | 8080  | Alert payload logs               |

## Failure Injection
```bash
# 100% errors
curl -X POST http://localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode": "error", "error_rate": 1.0}'

# 800ms latency
curl -X POST http://localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode": "latency", "latency_ms": 800}'

# Mixed
curl -X POST http://localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode": "mixed", "latency_ms": 500, "error_rate": 0.5}'

# Inspect state
curl http://localhost:8002/admin/state

# Reset
curl -X POST http://localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode": "none"}'
```

## SLO Design

Target: 99% success rate on service_a_requests_total (1% error budget).

| Alert | Windows | Burn Rate | Severity | Meaning |
|-------|---------|-----------|----------|---------|
| SLOServiceAErrorBudgetBurnFast | 5m + 1h  | >14.4x | page   | Budget gone in <1h  |
| SLOServiceAErrorBudgetBurnSlow | 30m + 6h | >6x    | ticket | Budget gone in <1d  |

Multi-window alerting: fast windows catch spikes, slow windows confirm sustained degradation.

See [RUNBOOK.md](./RUNBOOK.md) for alert meanings and mitigation steps.

## Architecture
```
Client
  │
  ▼
service_a (:8001)
  │  ── HTTP /compute ──▶  service_b (:8002)
  │                            │
  │               [failure injection: latency/error/mixed]
  │
  ├── OTLP traces ──▶ OTel Collector ──▶ Jaeger (:16686)
  │
  └── /metrics ──▶ Prometheus (:9090)
                        │
                        ├── rules ──▶ Alertmanager (:9093) ──▶ webhook (:8080)
                        └── PromQL ──▶ Grafana (:3000)
```

## Troubleshooting

**Port already in use** — remap in docker-compose.yml e.g. `"18001:8001"`

**Prometheus targets DOWN** — check `make ps`, then `curl localhost:8001/metrics`

**Grafana no data** — confirm Prometheus datasource connected, generate traffic first

**network not found on startup**
```bash
docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml down -v
docker network prune -f
docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml up -d --build
```

## CI

GitHub Actions smoke test on every push to main — builds from scratch, health-checks all services, verifies Prometheus targets and SLO rules loaded. See [.github/workflows/ci.yml](./.github/workflows/ci.yml).

## Stack Versions

| Component       | Image                                        |
|-----------------|----------------------------------------------|
| Python          | 3.11-slim                                    |
| OTel Collector  | otel/opentelemetry-collector:0.99.0          |
| Jaeger          | jaegertracing/all-in-one:1.56                |
| Prometheus      | prom/prometheus:v2.52.0                      |
| Alertmanager    | prom/alertmanager:v0.27.0                    |
| Grafana         | grafana/grafana:10.4.2                       |
