# otel-slo-guard-demo — Runbook (D09)

## Endpoints
- Service A: http://localhost:8001
- Service B: http://localhost:8002
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093
- Grafana: http://localhost:3000  (admin/admin)
- Jaeger: http://localhost:16686

## What it means when alerts fire
### HighErrorRate (ServiceAHighErrorRate / ServiceBHighErrorRate)
- Meaning: non-success requests occurred in the last minute.
- Confirm:
  - Prometheus query: `increase(service_a_requests_total{status!="success"}[1m])`
- Usual cause in this demo: Service B is in failmode error.

### SLO Burn Fast / Slow
- Meaning: error budget is being consumed too quickly.
- Fast window = urgent page; Slow window = ticket.
- Confirm:
  - burn rate metrics in Grafana panel
  - or Prometheus query:
    - `slo:service_a:burn_rate:5m`
    - `slo:service_a:burn_rate:1h`

## First actions (fast)
1) Check service health:
   - `curl -s localhost:8001/healthz; echo`
   - `curl -s localhost:8002/healthz; echo`

2) Check current failmode:
   - `curl -s localhost:8002/admin/state; echo`

3) If failmode is causing the incident, revert:
   - `curl -s -X POST localhost:8002/admin/failmode -H "Content-Type: application/json" -d '{"mode":"none","latency_ms":50,"error_rate":0.0}'; echo`

4) Verify recovery:
   - generate traffic, then watch alerts resolve
