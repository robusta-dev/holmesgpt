# ruff: noqa: F821
import logging
import time
from random import randint
from time import sleep

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORED_PROCEDURE = "sp_CheckUserNotifications"


# Add Prometheus middleware
Instrumentator().instrument(app).expose(app)


def check_promotional_notifications():
    logger.info(
        "Connecting to promotions database to see if we should try to upsell user"
    )
    try:
        logger.info("Successfully connected to database")
        start_time = time.time()
        logger.info(f"Fetching data using stored procedure: {STORED_PROCEDURE}")

        sleep(randint(5, 10))

        result = [(True, {"type": "notification", "discount": f"${randint(6,50)}"})]
        end_time = time.time()
        logger.info(f"Database call completed in {end_time - start_time:.2f} seconds.")
        for row in result:
            notifications = row[0]  # Access the first element of the tuple
            logger.info(f"Promotions result: {notifications}")
            return notifications
    except Exception as e:
        logger.error(f"Error checking for promotions: {e}")
        return False


@app.get("/", response_class=HTMLResponse)
def read_root():
    logger.info("Received request for checkout page.")
    start_time = time.time()
    has_promotions = check_promotional_notifications()
    end_time = time.time()
    logger.info(f"Page rendered in {end_time - start_time:.2f} seconds.")
    return f"""
    <html>
        <head>
            <title>Checkout Status</title>
        </head>
        <body>
            <h1>Success!</h1>
            <p>Promotions: {has_promotions}</p>
        </body>
    </html>
    """


if __name__ == "__main__":
    # Start Prometheus metrics server
    start_http_server(8001)
    uvicorn.run(app, host="0.0.0.0", port=8000)
