#!/usr/bin/env python3
import json
from datetime import datetime
import time
import random


def generate_log_entry(
    active_connections, max_connections=100, wait_time=None, error=None
):
    timestamp = datetime.utcnow()

    level = "INFO"
    message = f"Database pool status: {active_connections}/{max_connections} connections active"

    if error:
        level = "ERROR"
        message = error
    elif active_connections >= 95:
        level = "WARN"
        message = (
            f"Connection pool nearly exhausted: {active_connections}/{max_connections}"
        )
    elif active_connections >= 80:
        level = "WARN"
        message = f"High connection pool usage: {active_connections}/{max_connections}"

    entry = {
        "timestamp": timestamp.isoformat() + "Z",
        "level": level,
        "service": "backend-service",
        "component": "database-pool",
        "active_connections": active_connections,
        "max_connections": max_connections,
        "pool_usage_percent": round((active_connections / max_connections) * 100, 2),
        "message": message,
    }

    if wait_time:
        entry["connection_wait_ms"] = wait_time

    return json.dumps(entry)


def main():
    # Normal operation for first 50,000 logs (5-20 connections)
    for i in range(50000):
        connections = random.randint(5, 20)
        print(generate_log_entry(connections))

    # Gradual increase during peak hours (position: 50% through logs)
    for i in range(10000):
        # Gradually increase from 20 to 80 connections
        connections = 20 + int((i / 10000) * 60)
        wait_time = None if connections < 70 else random.randint(100, 500)
        print(generate_log_entry(connections, wait_time=wait_time))

    # Warning phase - approaching limit
    print(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "WARN",
                "service": "backend-service",
                "component": "database-pool",
                "message": "Connection wait time increasing: Average wait 500ms",
                "avg_wait_ms": 500,
                "active_connections": 80,
            }
        )
    )

    # Continue increasing to near limit
    for i in range(5000):
        connections = 80 + int((i / 5000) * 15)  # 80 to 95
        wait_time = random.randint(500, 2000)
        print(generate_log_entry(connections, wait_time=wait_time))

    # Critical phase - pool exhausted
    print(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "ERROR",
                "service": "backend-service",
                "component": "database-pool",
                "message": "Connection pool exhausted!",
                "active_connections": 100,
                "max_connections": 100,
                "rejected_requests": 0,
            }
        )
    )

    # Multiple timeout errors
    for i in range(1000):
        print(
            generate_log_entry(
                100,
                error="Timeout waiting for database connection after 30000ms - Pool exhausted (100/100)",
            )
        )

        # Some successful requests that managed to get connections
        if i % 10 == 0:
            print(generate_log_entry(100, wait_time=random.randint(25000, 30000)))

    # More normal logs after the incident
    for i in range(34000):
        connections = random.randint(5, 20)
        print(generate_log_entry(connections))

    # Keep pod running
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
