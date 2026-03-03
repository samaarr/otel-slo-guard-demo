#!/usr/bin/env bash
set -euo pipefail

echo "==> Setting service_b failmode = none"
curl -s -X POST localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode":"none","latency_ms":50,"error_rate":0.0}' | jq . || true
echo

echo "==> Generating healthy traffic (50 requests)"
for i in {1..50}; do curl -s localhost:8001/work > /dev/null; done

echo "==> Waiting 70s so 1m windows age out (burn rates drop)"
sleep 70

echo "==> Prometheus alerts"
curl -s localhost:9090/api/v1/alerts | head -n 250 || true
echo

echo "==> Alertmanager active alerts"
curl -s localhost:9093/api/v2/alerts | head -n 250 || true
echo
