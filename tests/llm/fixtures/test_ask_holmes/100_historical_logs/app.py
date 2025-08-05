#!/usr/bin/env python3
import os
import time
import json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import random

# Set random seed for reproducible logs
random.seed(100)


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
    with open("/var/log/payment-api.log", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
        f.flush()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "healthy", "uptime_seconds": 60}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Log health checks occasionally
        if random.random() < 0.1:
            log_structured(
                "INFO",
                "Health check passed",
                endpoint="/healthz",
                response_time_ms=random.randint(50, 200),
            )


def generate_historical_logs():
    """Generate all historical logs including the incident period."""
    # Define the problematic period
    problem_start = datetime(2025, 8, 2, 13, 45, 0)
    problem_end = datetime(2025, 8, 2, 14, 45, 0)

    # Generate logs from August 1 to August 4
    current_time = datetime(2025, 8, 1, 0, 0, 0)
    scenario_now = datetime(2025, 8, 4, 14, 0, 0)

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
                processing_time_ms=random.randint(100, 500),
            )

        if random.random() < 0.05:
            log_structured(
                "INFO",
                "User authenticated",
                timestamp=current_time,
                user_id=f"USER-{random.randint(100, 999)}",
                method="oauth2",
                ip_address=f"192.168.{random.randint(1,254)}.{random.randint(1,254)}",
            )

        # Database query logs
        if random.random() < 0.2:
            query_time = random.randint(10, 100)
            if problem_start <= current_time <= problem_end:
                query_time = random.randint(1000, 5000)  # Slow queries during issues

            log_structured(
                "DEBUG",
                "Database query executed",
                timestamp=current_time,
                query="SELECT * FROM payments WHERE status = ?",
                duration_ms=query_time,
                rows_returned=random.randint(0, 100),
            )

        # Cache operations
        if random.random() < 0.15:
            log_structured(
                "DEBUG",
                "Cache operation",
                timestamp=current_time,
                operation=random.choice(["get", "set", "expire"]),
                key=f"user:{random.randint(100, 999)}:profile",
                hit=random.choice([True, False]),
            )

        # During incident period, generate the specific errors
        if problem_start <= current_time <= problem_end:
            # Connection pool exhaustion errors
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

            # Health check failures with specific error
            if random.random() < 0.2:
                log_structured(
                    "ERROR",
                    "Liveness probe failed - health check timeout",
                    timestamp=current_time,
                    endpoint="/healthz",
                    timeout_ms=10000,
                    error="ConnectionPoolExhausted",
                )

            # Simulate consecutive probe failures occasionally
            if random.random() < 0.1:
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

        # Advance time
        current_time += timedelta(seconds=random.randint(10, 30))


def main():
    # Generate all historical logs first
    log_thread = threading.Thread(target=generate_historical_logs, daemon=True)
    log_thread.start()

    # Give time for historical logs to be written
    time.sleep(2)

    # Start health endpoint server
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    log_structured("INFO", "Payment API started", port=8080, version="1.2.3")

    # Add startup logs
    log_structured(
        "INFO",
        "Initializing database connection pool",
        pool_size=20,
        min_connections=5,
        max_connections=50,
    )
    log_structured(
        "INFO",
        "Database connection established",
        host="postgres-primary",
        port=5432,
        database="payments",
    )
    log_structured(
        "INFO", "Connection pool initialized", active_connections=5, idle_connections=15
    )
    log_structured(
        "INFO",
        "Loading configuration from environment",
        config_source="env",
        vars_loaded=42,
    )
    log_structured(
        "INFO", "Initializing Redis cache client", host="redis-master", port=6379
    )
    log_structured(
        "INFO",
        "Payment gateway connection test",
        status="success",
        response_time_ms=245,
    )
    log_structured(
        "INFO",
        "Starting background workers",
        workers=["payment-processor", "fraud-detector", "webhook-sender"],
    )

    # Initial database queries
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
    ]

    for query, rows, duration in queries:
        log_structured(
            "DEBUG",
            "Database query executed",
            query=query,
            rows_returned=rows,
            duration_ms=duration,
        )

    log_structured("INFO", "Application initialization complete", startup_time_ms=2150)

    # Generate real-time logs with variety
    def real_time_logs():
        while True:
            log_type = random.random()
            if log_type < 0.6:
                log_structured(
                    "INFO",
                    "Payment processed successfully",
                    payment_id=f"PAY-{random.randint(1000, 9999)}",
                    amount=round(random.uniform(10, 1000), 2),
                    currency="USD",
                    processing_time_ms=random.randint(100, 500),
                )
            elif log_type < 0.75:
                log_structured(
                    "DEBUG",
                    "Database query executed",
                    query="SELECT * FROM payments WHERE user_id = ?",
                    duration_ms=random.randint(5, 50),
                    rows_returned=random.randint(0, 10),
                )
            elif log_type < 0.85:
                log_structured(
                    "INFO",
                    "User authenticated",
                    user_id=f"USER-{random.randint(100, 999)}",
                    method=random.choice(["oauth2", "api_key", "jwt"]),
                )
            elif log_type < 0.95:
                log_structured(
                    "DEBUG",
                    "Cache operation",
                    operation=random.choice(["get", "set"]),
                    key=f"session:{random.randint(1000, 9999)}",
                    hit=random.choice([True, False]),
                )
            time.sleep(random.randint(3, 8))

    rt_thread = threading.Thread(target=real_time_logs, daemon=True)
    rt_thread.start()

    server.serve_forever()


if __name__ == "__main__":
    main()
