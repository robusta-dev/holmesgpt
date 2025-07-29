#!/usr/bin/env python3
import time
import random
from datetime import datetime
import sys


def generate_web_logs():
    """Generate web container logs with performance metrics."""
    pages = ["/orders", "/checkout", "/products"]

    # Generate 100 sets of logs
    for _ in range(100):
        for i, page in enumerate(pages):
            # Generate render times: 7-9 seconds based on page index
            base_time = 7 + i
            render_time = base_time + random.randint(100, 999) / 1000

            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

            # Generate logs that don't directly reveal the pattern
            print(f"[{timestamp}] GET {page} 200 OK")
            print(f"[{timestamp}] Performance metric recorded: page_render_complete")
            print(
                f"[{timestamp}] Request completed - duration={int(render_time * 1000)}ms"
            )

            # Add some noise logs
            print(f"[{timestamp}] Connection from 10.0.0.{random.randint(1, 255)}")
            print(f"[{timestamp}] Cache hit ratio: {random.randint(70, 95)}%")


def generate_metrics_logs():
    """Generate metrics container logs."""
    # Generate 300 metric entries
    for _ in range(300):
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        print(f"[{timestamp}] Metrics collected", flush=True)
        print(f"[{timestamp}] CPU usage: {random.randint(10, 30)}%", flush=True)
        print(f"[{timestamp}] Memory usage: {random.randint(100, 200)}MB", flush=True)


if __name__ == "__main__":
    container = sys.argv[1] if len(sys.argv) > 1 else "web"

    if container == "web":
        generate_web_logs()
    elif container == "metrics":
        generate_metrics_logs()

    while True:
        time.sleep(1000)
