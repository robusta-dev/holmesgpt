#!/usr/bin/env python3
import time
import requests
import logging
import random

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_URL = (
    "http://metrics-collector.production-telemetry.svc.cluster.local:8080/api/process"
)
REQUEST_TIMEOUT = 5  # 5 second timeout as specified
REQUEST_INTERVAL = 0.05  # 50ms between requests for ~20 requests/second


def main():
    logger.info("Service starting...")
    logger.info("Initializing connections...")

    # Wait a moment to ensure everything is initialized
    time.sleep(2)

    while True:
        try:
            # Make request with timeout
            start_time = time.time()
            response = requests.post(
                BACKEND_URL,
                json={
                    "data_batch_id": f"batch-{random.randint(1000, 9999)}",
                    "records": random.randint(50, 200),
                    "processing_type": random.choice(["standard", "priority", "bulk"]),
                },
                timeout=REQUEST_TIMEOUT,
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Processed {data.get('processed_items', 0)} items in {elapsed:.3f}s"
                )
            else:
                logger.warning(f"Received status {response.status_code}")

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
            logger.error("Processing failed: Request timed out")
        except Exception as e:
            logger.error(f"Processing failed: {e}")

        # Brief pause between requests
        time.sleep(REQUEST_INTERVAL)


if __name__ == "__main__":
    main()
