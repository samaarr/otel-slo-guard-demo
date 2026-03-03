#!/usr/bin/env bash
set -euo pipefail

echo "==> Setting service_b failmode = none"
curl -s -X POST localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode":"none","latency_ms":50,"error_rate":0.0}' | jq . || true
echo

echo "==> Generating success traffic (50 requests)"
for i in {1..50}; do curl -s localhost:8001/work > /dev/null; done

echo "==> Quick metric sanity check"
echo "-- service_a_requests_total"
curl -s localhost:8001/metrics | grep -E 'service_a_requests_total' | head -n 20 || true
echo
echo "-- service_b_requests_total"
curl -s localhost:8002/metrics | grep -E 'service_b_requests_total' | head -n 20 || true
echo

echo "==> Prometheus query sample"
curl -s "http://localhost:9090/api/v1/query?query=service_a_requests_total" | head -n 40 || true
echo
