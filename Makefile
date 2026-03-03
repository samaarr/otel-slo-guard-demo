SHELL := /bin/bash

.PHONY: up down rebuild logs ps demo-success demo-error reset targets rules alerts am-alerts grafana prometheus jaeger

up:
	docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml up -d --build

down:
	docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml down -v

rebuild:
	docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml up -d --build --force-recreate

logs:
	docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml logs -f --tail=200

ps:
	docker compose -f docker-compose.yml -f docker-compose.prometheus.override.yml ps

# quick demos
demo-success:
	./scripts/demo_success.sh

demo-error:
	./scripts/demo_error_burst.sh

reset:
	./scripts/reset_demo.sh

# quick checks
targets:
	curl -s localhost:9090/api/v1/targets | grep -E '"job"|"health"|"scrapeUrl"' | head -n 200

rules:
	curl -s localhost:9090/api/v1/rules | head -n 200

alerts:
	curl -s localhost:9090/api/v1/alerts | head -n 250

am-alerts:
	curl -s localhost:9093/api/v2/alerts | head -n 250

# open UIs (macOS friendly)
grafana:
	open http://localhost:3000 || true

prometheus:
	open http://localhost:9090 || true

jaeger:
	open http://localhost:16686 || true
