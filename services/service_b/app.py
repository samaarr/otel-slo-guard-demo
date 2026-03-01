from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import random
import time
import threading

from telemetry import setup_tracing

app = FastAPI(title="Service B")
setup_tracing(app, service_name="service_b")

_state_lock = threading.Lock()
_state = {
    "mode": "none",
    "latency_ms": 100,
    "error_rate": 0.0,
}

class FailModeUpdate(BaseModel):
    mode: str = Field(..., description="none|latency|error|mixed")
    latency_ms: int = Field(100, ge=0, le=10000)
    error_rate: float = Field(0.0, ge=0.0, le=1.0)

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "B"}

@app.get("/admin/state")
def get_state():
    with _state_lock:
        return {"service": "B", **_state}

@app.post("/admin/failmode")
def set_failmode(update: FailModeUpdate):
    mode = update.mode.strip().lower()
    if mode not in {"none", "latency", "error", "mixed"}:
        raise HTTPException(status_code=400, detail="mode must be one of: none, latency, error, mixed")

    with _state_lock:
        _state["mode"] = mode
        _state["latency_ms"] = update.latency_ms
        _state["error_rate"] = update.error_rate

    return {"ok": True, "updated": {"service": "B", **_state}}

@app.get("/compute")
def compute():
    with _state_lock:
        mode = _state["mode"]
        latency_ms = _state["latency_ms"]
        error_rate = _state["error_rate"]

    if mode in {"latency", "mixed"} and latency_ms > 0:
        time.sleep(latency_ms / 1000.0)

    if mode in {"error", "mixed"} and error_rate > 0.0:
        if random.random() < error_rate:
            raise HTTPException(status_code=500, detail="Injected failure from Service B")

    return {
        "result": "processed by B",
        "mode": mode,
        "latency_ms": latency_ms,
        "error_rate": error_rate,
    }
