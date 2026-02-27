from fastapi import FastAPI
import time

app = FastAPI(title="Service B")

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "B"}

@app.get("/compute")
def compute():
    # Simulate small processing time
    time.sleep(0.1)
    return {"result": "processed by B"}