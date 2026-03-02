import os
import requests
from fastapi import FastAPI

from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from telemetry import setup_tracing

app = FastAPI(title="service_a")
setup_tracing(app, service_name="service_a")

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://service_b:8002") + "/compute"
TIMEOUT_S = 0.5

service_a_requests_total = Counter(
    "service_a_requests_total",
    "Total requests to service A",
    ["endpoint", "method", "status"],
)

service_a_dependency_calls_total = Counter(
    "service_a_dependency_calls_total",
    "Calls from service A to dependencies",
    ["dependency", "endpoint", "status"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/work")
def work():
    endpoint = "/work"
    method = "GET"

    try:
        r = requests.get(SERVICE_B_URL, timeout=TIMEOUT_S)
        r.raise_for_status()

        service_a_dependency_calls_total.labels("service_b", "/compute", "success").inc()
        service_a_requests_total.labels(endpoint, method, "success").inc()
        return {"status": "ok", "service_b": r.json()}

    except requests.exceptions.Timeout:
        service_a_dependency_calls_total.labels("service_b", "/compute", "timeout").inc()
        service_a_requests_total.labels(endpoint, method, "timeout").inc()
        return {"status": "error", "reason": "timeout"}

    except Exception:
        service_a_dependency_calls_total.labels("service_b", "/compute", "error").inc()
        service_a_requests_total.labels(endpoint, method, "request_failed").inc()
        return {"status": "error", "reason": "request_failed"}
