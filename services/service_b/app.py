from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import random
import time

from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from telemetry import setup_tracing

app = FastAPI(title="service_b")
setup_tracing(app, service_name="service_b")

service_b_requests_total = Counter(
    "service_b_requests_total",
    "Total requests to service B",
    ["endpoint", "method", "status"],
)

STATE = {"mode": "none", "latency_ms": 50, "error_rate": 0.0}


class FailMode(BaseModel):
    mode: str
    latency_ms: int = 50
    error_rate: float = 0.0


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/state")
def admin_state():
    return STATE


@app.post("/admin/failmode")
def set_failmode(cfg: FailMode):
    STATE["mode"] = cfg.mode
    STATE["latency_ms"] = cfg.latency_ms
    STATE["error_rate"] = cfg.error_rate
    return {"ok": True, "state": STATE}


@app.get("/compute")
def compute():
    endpoint = "/compute"
    method = "GET"

    mode = STATE["mode"]
    latency_ms = STATE["latency_ms"]
    error_rate = STATE["error_rate"]

    if mode in {"slow", "mixed"} and latency_ms > 0:
        time.sleep(latency_ms / 1000.0)

    if mode in {"error", "mixed"} and error_rate > 0.0:
        if random.random() < error_rate:
            service_b_requests_total.labels(endpoint, method, "error").inc()
            raise HTTPException(status_code=500, detail="Injected failure from Service B")

    service_b_requests_total.labels(endpoint, method, "success").inc()
    return {"result": "processed by B", "mode": mode, "latency_ms": latency_ms, "error_rate": error_rate}
