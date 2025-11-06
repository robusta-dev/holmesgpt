#!/usr/bin/env python3
import time
import random
from flask import Flask, jsonify
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize request counter and stuck threshold
request_count = 0
stuck_after = random.randint(100, 200)
logger.info("Service initialized")


@app.route("/api/process", methods=["GET", "POST"])
def process_data():
    global request_count
    request_count += 1

    # Log each request
    logger.info("got request")

    # Check if we should get stuck
    if request_count >= stuck_after:
        # Enter stuck state - no logs, just hang forever
        while True:
            time.sleep(3600)  # Sleep for an hour, repeatedly

    # Normal operation - return some data
    response_data = {
        "status": "success",
        "processed_items": random.randint(10, 100),
        "timestamp": time.time(),
        "metrics": {
            "cpu_usage": round(random.uniform(20, 40), 2),
            "memory_mb": random.randint(100, 200),
        },
    }

    # Simulate some processing time
    time.sleep(random.uniform(0.01, 0.05))

    return jsonify(response_data)


@app.route("/health", methods=["GET"])
def health_check():
    # Health check continues to work even when stuck
    return jsonify({"status": "healthy", "uptime": time.time()})


if __name__ == "__main__":
    logger.info("Starting service on port 8080")
    app.run(host="0.0.0.0", port=8080)
