#!/usr/bin/env python3
"""
Sample API service that simulates slow responses due to resource constraints.
This app will be deployed with low CPU limits to trigger throttling.
"""

import time
import os
import signal
import sys
from flask import Flask, jsonify
import psutil

app = Flask(__name__)

# Global flag for health check status
healthy = True
startup_time = time.time()


def cpu_intensive_task():
    """Perform CPU-intensive calculations"""
    result = 0
    for i in range(1000000):
        result += i**2
    return result


@app.route("/health")
def health():
    """Health check endpoint - fails after initial grace period"""
    # Simulate failing health checks after 30 seconds
    if time.time() - startup_time > 30:
        return jsonify(
            {"status": "unhealthy", "reason": "CPU throttling detected"}
        ), 503
    return jsonify({"status": "healthy"}), 200


@app.route("/ready")
def ready():
    """Readiness check endpoint"""
    if not healthy:
        return jsonify({"status": "not ready", "reason": "Application overloaded"}), 503
    return jsonify({"status": "ready"}), 200


@app.route("/api/compute")
def compute():
    """CPU-intensive endpoint that will be slow under resource constraints"""
    start_time = time.time()

    # Perform CPU-intensive task
    result = cpu_intensive_task()

    duration = time.time() - start_time

    # If request takes too long, mark as unhealthy
    if duration > 5:
        global healthy
        healthy = False

    return jsonify(
        {
            "result": result,
            "duration_seconds": duration,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
        }
    )


@app.route("/api/status")
def status():
    """Status endpoint to check application state"""
    return jsonify(
        {
            "uptime_seconds": time.time() - startup_time,
            "healthy": healthy,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "pid": os.getpid(),
        }
    )


@app.route("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    # Simple metrics in Prometheus format
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory_usage = psutil.virtual_memory().percent

    metrics_text = f"""# HELP api_request_duration_seconds API request duration in seconds
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="0.5"}} 0
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="1.0"}} 2
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="2.5"}} 5
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="5.0"}} 15
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="10.0"}} 45
api_request_duration_seconds_bucket{{endpoint="/api/compute",le="+Inf"}} 50
api_request_duration_seconds_sum{{endpoint="/api/compute"}} 375.5
api_request_duration_seconds_count{{endpoint="/api/compute"}} 50

# HELP api_requests_total Total number of API requests
# TYPE api_requests_total counter
api_requests_total{{endpoint="/api/compute",status="200"}} 45
api_requests_total{{endpoint="/api/compute",status="500"}} 5

# HELP process_cpu_usage CPU usage percentage
# TYPE process_cpu_usage gauge
process_cpu_usage {cpu_usage}

# HELP process_memory_usage Memory usage percentage
# TYPE process_memory_usage gauge
process_memory_usage {memory_usage}
"""
    return metrics_text, 200, {"Content-Type": "text/plain"}


def signal_handler(sig, frame):
    print("Shutting down gracefully...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    port = int(os.environ.get("PORT", 8080))
    print(f"Starting ocean-api server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
