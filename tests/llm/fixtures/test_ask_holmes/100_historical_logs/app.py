#!/usr/bin/env python3
import os
import time
import json
import logging
import random
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Set random seed for reproducible logs
random.seed(143)

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Track application state
app_start_time = datetime.utcnow()
request_count = 0


def log_structured(level, message, timestamp=None, **kwargs):
    """Log in structured format for Loki."""
    if timestamp is None:
        timestamp = datetime.utcnow()

    log_entry = {
        "timestamp": timestamp.isoformat() + "Z",
        "level": level,
        "message": message,
        "service": "payment-api",
        "pod": os.environ.get("HOSTNAME", "payment-api-pod"),
        **kwargs,
    }
    # Write to log file for Promtail to pick up
    with open("/var/log/payment-api.log", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
        f.flush()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global request_count
        request_count += 1

        if self.path == "/healthz":
            current_time = datetime.utcnow()
            time_since_start = (current_time - app_start_time).total_seconds()

            log_structured(
                "INFO",
                "Health check passed",
                endpoint="/healthz",
                response_time_ms=random.randint(50, 200),
            )

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "status": "healthy",
                "uptime_seconds": int(time_since_start),
                "request_count": request_count,
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()


def simulate_application_logs():
    try:
        # Define the problematic period - August 2, 2025 13:45-14:45 UTC
        problem_start = datetime(2025, 8, 2, 13, 45, 0)
        problem_end = datetime(2025, 8, 2, 14, 45, 0)

        # Generate historical logs starting from August 1, 2025
        current_time = datetime(2025, 8, 1, 0, 0, 0)

        # First, write all historical logs up to current time
        # Use a fixed end time to ensure we generate logs up to "now" in the scenario
        scenario_now = datetime(2025, 8, 4, 14, 0, 0)  # Current time in the scenario
        while current_time < scenario_now:
            # Normal operation logs
            if random.random() < 0.1:
                log_structured(
                    "INFO",
                    "Payment processed successfully",
                    timestamp=current_time,
                    payment_id=f"PAY-{random.randint(1000, 9999)}",
                    amount=round(random.uniform(10, 1000), 2),
                    currency="USD",
                )

            if random.random() < 0.05:
                log_structured(
                    "INFO",
                    "User authenticated",
                    timestamp=current_time,
                    user_id=f"USER-{random.randint(100, 999)}",
                    method="oauth2",
                )

            # Simulate connection pool issues during the problematic hour
            if problem_start <= current_time <= problem_end:
                # Frequent connection pool warnings
                if random.random() < 0.4:
                    log_structured(
                        "ERROR",
                        "Failed to acquire database connection - pool exhausted",
                        timestamp=current_time,
                        wait_time_ms=random.randint(1000, 5000),
                        queue_length=random.randint(5, 15),
                    )

                if random.random() < 0.1:
                    log_structured(
                        "ERROR",
                        "Transaction rollback due to connection timeout",
                        timestamp=current_time,
                        transaction_id=f"TXN-{random.randint(10000, 99999)}",
                        error="ConnectionTimeout",
                    )

                # Simulate liveness probe failures
                if random.random() < 0.2:
                    log_structured(
                        "ERROR",
                        "Liveness probe failed - health check timeout",
                        timestamp=current_time,
                        endpoint="/healthz",
                        timeout_ms=10000,
                        error="ConnectionPoolExhausted",
                    )

                # Simulate consecutive probe failures leading to restart
                if random.random() < 0.1:
                    # Log 3 consecutive failures
                    for i in range(3):
                        probe_time = current_time + timedelta(seconds=i * 10)
                        log_structured(
                            "ERROR",
                            f"Liveness probe failed ({i+1}/3)",
                            timestamp=probe_time,
                            endpoint="/healthz",
                            failure_count=i + 1,
                            failure_threshold=3,
                            error="HealthCheckTimeout",
                        )

            # Regular database queries
            if random.random() < 0.2:
                query_time = random.randint(10, 100)
                if problem_start <= current_time <= problem_end:
                    query_time = random.randint(
                        1000, 5000
                    )  # Slow queries during issues

                log_structured(
                    "DEBUG",
                    "Database query executed",
                    timestamp=current_time,
                    query="SELECT * FROM payments WHERE status = ?",
                    duration_ms=query_time,
                    rows_returned=random.randint(0, 100),
                )

            # Advance time for historical logs
            current_time += timedelta(seconds=random.randint(10, 30))

        # Now generate real-time logs with scenario time
        while True:
            if random.random() < 0.1:
                log_structured(
                    "INFO",
                    "Payment processed successfully",
                    payment_id=f"PAY-{random.randint(1000, 9999)}",
                    amount=round(random.uniform(10, 1000), 2),
                    currency="USD",
                )
            time.sleep(5)
    except Exception as e:
        # Log the error so we can see what went wrong
        print(f"Error in log generation thread: {e}")
        import traceback

        traceback.print_exc()


def main():
    # time.sleep(30) # wait for promtail to start (possibly not necessary)

    log_thread = threading.Thread(target=simulate_application_logs, daemon=True)
    log_thread.start()

    # Give time for historical logs to be written
    time.sleep(2)

    # Start health endpoint server
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    log_structured("INFO", "Payment API started", port=8080, version="1.2.3")

    # Generate realistic startup activity - connection pool init, cache warming, etc.
    log_structured(
        "INFO",
        "Initializing database connection pool",
        pool_size=20,
        min_connections=5,
        max_connections=50,
    )

    # Simulate realistic startup activities
    startup_activities = [
        (
            "Database connection established",
            {"host": "postgres-primary", "port": 5432, "database": "payments"},
        ),
        (
            "Connection pool initialized",
            {"active_connections": 5, "idle_connections": 15},
        ),
        (
            "Loading configuration from environment",
            {"config_source": "env", "vars_loaded": 42},
        ),
        ("Initializing Redis cache client", {"host": "redis-master", "port": 6379}),
        ("Cache connection established", {"latency_ms": 2}),
        (
            "Loading payment gateway certificates",
            {"provider": "stripe", "cert_expiry": "2026-08-04"},
        ),
        (
            "Payment gateway connection test",
            {"status": "success", "response_time_ms": 245},
        ),
        ("Initializing metrics collector", {"backend": "prometheus", "port": 9090}),
        ("Loading fraud detection rules", {"rules_count": 127, "version": "2.3.1"}),
        ("Warming up cache with frequently accessed data", {"entries_loaded": 0}),
    ]

    # Execute startup activities
    for activity, metadata in startup_activities:
        log_structured("INFO", activity, **metadata)
        time.sleep(0.001)  # Small delay to ensure log ordering

    # Simulate cache warming with payment data
    for i in range(50):
        log_structured(
            "DEBUG",
            "Cache warming progress",
            entries_loaded=i * 20,
            total_entries=1000,
            cache_hit_rate=0.0,
        )

    # Simulate initial database queries
    queries = [
        (
            "SELECT COUNT(*) FROM payments WHERE created_at > NOW() - INTERVAL '24 hours'",
            156,
            23,
        ),
        (
            "SELECT * FROM payment_methods WHERE active = true ORDER BY last_used DESC LIMIT 100",
            100,
            45,
        ),
        (
            "SELECT COUNT(*) FROM users WHERE last_login > NOW() - INTERVAL '7 days'",
            1,
            12,
        ),
        ("SELECT * FROM fraud_rules WHERE enabled = true", 127, 67),
        ("SELECT * FROM merchant_accounts WHERE status = 'active'", 43, 34),
    ]

    for query, rows, duration in queries:
        log_structured(
            "DEBUG",
            "Database query executed",
            query=query,
            rows_returned=rows,
            duration_ms=duration,
        )

    # Simulate initial health checks and monitoring setup
    log_structured(
        "INFO",
        "Health check endpoint initialized",
        endpoint="/healthz",
        interval_seconds=10,
    )
    log_structured(
        "INFO", "Metrics endpoint initialized", endpoint="/metrics", scrape_interval=15
    )
    log_structured(
        "INFO",
        "Starting background workers",
        workers=["payment-processor", "fraud-detector", "webhook-sender"],
    )

    # Generate normal operational logs to fill up log buffer
    for i in range(900):
        log_type = random.choice(
            [("payment", 0.6), ("auth", 0.2), ("cache", 0.15), ("db_query", 0.05)]
        )

        if log_type[0] == "payment" and random.random() < log_type[1]:
            log_structured(
                "INFO",
                "Payment processed successfully",
                payment_id=f"PAY-{random.randint(1000, 9999)}",
                amount=round(random.uniform(10, 1000), 2),
                currency="USD",
                processing_time_ms=random.randint(100, 500),
            )
        elif log_type[0] == "auth" and random.random() < log_type[1]:
            log_structured(
                "INFO",
                "User authenticated",
                user_id=f"USER-{random.randint(100, 999)}",
                method=random.choice(["oauth2", "api_key", "jwt"]),
                ip_address=f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",
            )
        elif log_type[0] == "cache" and random.random() < log_type[1]:
            log_structured(
                "DEBUG",
                "Cache operation",
                operation=random.choice(["get", "set", "expire"]),
                key=f"user:{random.randint(100, 999)}:profile",
                hit=random.choice([True, False]),
            )
        elif log_type[0] == "db_query" and random.random() < log_type[1]:
            log_structured(
                "DEBUG",
                "Database query executed",
                query="SELECT * FROM payments WHERE user_id = ?",
                duration_ms=random.randint(5, 50),
                rows_returned=random.randint(0, 10),
            )

    log_structured(
        "INFO",
        "Application initialization complete",
        startup_time_ms=int(
            (datetime.utcnow() - app_start_time).total_seconds() * 1000
        ),
    )

    server.serve_forever()


if __name__ == "__main__":
    main()
