#!/usr/bin/env bash
set -euo pipefail

echo "==> Setting service_b failmode = error (100%)"
curl -s -X POST localhost:8002/admin/failmode \
  -H "Content-Type: application/json" \
  -d '{"mode":"error","latency_ms":50,"error_rate":1.0}' | jq . || true
echo

echo "==> Generating error traffic (~120 requests paced)"
for i in {1..120}; do
  curl -s localhost:8001/work > /dev/null
  sleep 0.2
done

echo "==> Waiting 20s for rule evaluation + alert routing"
sleep 20

echo "==> Prometheus alerts (should show firing if thresholds met)"
curl -s localhost:9090/api/v1/alerts | head -n 250 || true
echo

echo "==> Alertmanager active alerts"
curl -s localhost:9093/api/v2/alerts | head -n 250 || true
echo

echo "==> Tip: check webhook logs"
echo "docker logs alertmanager-webhook --tail 200"
