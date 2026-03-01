from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import random
import time
import threading

app = FastAPI(title="Service B")

# --- Failure state (thread-safe) ---
_state_lock = threading.Lock()
_state = {
    "mode": "none",        # none | latency | error | mixed
    "latency_ms": 100,     # added latency in milliseconds
    "error_rate": 0.0,     # 0.0 to 1.0 probability of returning 500
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
    # Snapshot current state quickly under lock
    with _state_lock:
        mode = _state["mode"]
        latency_ms = _state["latency_ms"]
        error_rate = _state["error_rate"]

    # Inject latency
    if mode in {"latency", "mixed"} and latency_ms > 0:
        time.sleep(latency_ms / 1000.0)

    # Inject errors
    if mode in {"error", "mixed"} and error_rate > 0.0:
        if random.random() < error_rate:
            raise HTTPException(status_code=500, detail="Injected failure from Service B")

    # Normal response
    return {
        "result": "processed by B",
        "mode": mode,
        "latency_ms": latency_ms,
        "error_rate": error_rate,
    }
