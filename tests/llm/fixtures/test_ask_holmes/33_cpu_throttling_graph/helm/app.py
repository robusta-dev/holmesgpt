# ruff: noqa: F821
import logging
import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import bcrypt
import json

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Instrumentator().instrument(app).expose(app)


def verify_password():
    logger.info(
        "Connecting to promotions database to see if we should try to upsell user"
    )
    try:
        start_time = time.time()
        logger.info("Verify password")

        password = b"test_password"
        salt = bcrypt.gensalt(rounds=15)
        bcrypt.hashpw(password, salt)

        end_time = time.time()
        logger.info(
            f"Password verification completed in {end_time - start_time:.2f} seconds."
        )

        return True
    except Exception as e:
        logger.error(f"Error checking for password: {e}")
        return False


@app.get("/", response_class=JSONResponse)
def read_root():
    logger.info("Received request for checkout page.")
    start_time = time.time()
    is_valid = verify_password()
    end_time = time.time()
    logger.info(f"Page rendered in {end_time - start_time:.2f} seconds.")
    return json.dumps({"valid": is_valid})


if __name__ == "__main__":
    # Start Prometheus metrics server
    start_http_server(8001)
    uvicorn.run(app, host="0.0.0.0", port=8000)
