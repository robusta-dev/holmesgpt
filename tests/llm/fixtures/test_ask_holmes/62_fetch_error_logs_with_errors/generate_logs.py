#!/usr/bin/env python3
import time
from datetime import datetime
import random


def generate_logs():
    """Generate logs with database connection errors."""

    # Initial startup logs
    print(f"{datetime.now()} INFO: Application starting up")
    print(f"{datetime.now()} INFO: Connecting to database")
    print(f"{datetime.now()} WARN: Database connection slow")

    # Generate database errors without revealing exact messages
    print(f"{datetime.now()} ERROR: Database connection failed: ETIMEDOUT")
    print(f"{datetime.now()} ERROR: Attempting reconnection (attempt 1/3)")
    print(f"{datetime.now()} ERROR: Connection retry failed (attempt 2/3)")
    print(f"{datetime.now()} ERROR: Maximum retry attempts exceeded")
    print(f"{datetime.now()} INFO: Switching to backup database")
    print(f"{datetime.now()} ERROR: Backup connection failed: ECONNREFUSED")
    print(f"{datetime.now()} ERROR: Unable to establish database connection")
    print(f"{datetime.now()} FATAL: Shutting down application")

    # Keep running and generate occasional logs
    while True:
        time.sleep(60)
        if random.random() < 0.3:
            print(f"{datetime.now()} INFO: Health check requested")


if __name__ == "__main__":
    generate_logs()
