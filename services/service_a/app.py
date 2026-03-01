from fastapi import FastAPI
import requests
import logging
import os

app = FastAPI(title="Service A")
logging.basicConfig(level=logging.INFO)

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://service_b:8002")

@app.get("/healthz")
def health():
    return {"status": "ok", "service": "A"}

@app.get("/work")
def do_work():
    try:
        logging.info("Calling Service B...")
        response = requests.get(
            f"{SERVICE_B_URL}/compute",
            timeout=2
        )
        response.raise_for_status()
        data = response.json()

        return {"status": "success", "from_b": data}

    except requests.exceptions.Timeout:
        logging.error("Timeout when calling Service B")
        return {"status": "error", "reason": "timeout"}

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        logging.error(f"Service B returned HTTP {status}")
        return {"status": "error", "reason": "dependency_http_error", "code": status}

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return {"status": "error", "reason": "request_failed"}