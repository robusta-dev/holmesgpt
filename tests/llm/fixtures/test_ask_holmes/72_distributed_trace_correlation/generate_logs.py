#!/usr/bin/env python3
import json
from datetime import datetime
import time
import random
import uuid

services = [
    "order-tracker",
    "inventory-service",
    "shipping-service",
    "notification-service",
    "billing-service",
]


def generate_trace_id():
    return f"trace-{uuid.uuid4().hex[:16]}"


def generate_log_entry(
    service, level, message, trace_id=None, order_id=None, duration_ms=None
):
    timestamp = datetime.utcnow()

    entry = {
        "timestamp": timestamp.isoformat() + "Z",
        "level": level,
        "service": service,
        "message": message,
    }

    if trace_id:
        entry["trace_id"] = trace_id
    if order_id:
        entry["order_id"] = order_id
    if duration_ms:
        entry["duration_ms"] = duration_ms

    return json.dumps(entry)


def generate_successful_trace():
    trace_id = generate_trace_id()
    order_id = f"ORD-{random.randint(10000, 99999)}"

    logs = []
    # Service A: Order received
    logs.append(
        generate_log_entry(
            "order-tracker",
            "INFO",
            f"Order {order_id} received",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service B: Inventory check
    logs.append(
        generate_log_entry(
            "inventory-service",
            "INFO",
            f"Checking inventory for order {order_id}",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service C: Shipping
    logs.append(
        generate_log_entry(
            "shipping-service",
            "INFO",
            f"Calculating shipping for order {order_id}",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service D: Billing
    logs.append(
        generate_log_entry(
            "billing-service",
            "INFO",
            f"Processing payment for order {order_id}",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service E: Notification
    logs.append(
        generate_log_entry(
            "notification-service",
            "INFO",
            f"Order {order_id} confirmed, sending notification",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    return logs


def generate_failed_trace_for_order_12345():
    trace_id = "trace-ord12345failed"
    order_id = "ORD-12345"

    logs = []

    # Service A: Order received
    logs.append(
        generate_log_entry(
            "order-tracker",
            "INFO",
            f"Order {order_id} received from customer",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service B: Inventory check - OK
    logs.append(
        generate_log_entry(
            "inventory-service",
            "INFO",
            f"Inventory check passed for order {order_id}",
            trace_id=trace_id,
            order_id=order_id,
            duration_ms=145,
        )
    )

    # Service C: Shipping - OK
    logs.append(
        generate_log_entry(
            "shipping-service",
            "INFO",
            f"Shipping calculation completed for order {order_id}",
            trace_id=trace_id,
            order_id=order_id,
            duration_ms=230,
        )
    )

    # Service D: Billing - FAILS
    logs.append(
        generate_log_entry(
            "billing-service",
            "ERROR",
            f"Payment processing failed for order {order_id}: Credit card declined - Insufficient funds",
            trace_id=trace_id,
            order_id=order_id,
            duration_ms=3450,
        )
    )

    # Order tracker logs the failure
    logs.append(
        generate_log_entry(
            "order-tracker",
            "ERROR",
            f"Order {order_id} failed: Payment declined in billing-service",
            trace_id=trace_id,
            order_id=order_id,
        )
    )

    # Service E: Never reached
    # No notification service logs for this trace

    return logs


def main():
    all_logs = []

    # Generate 100,000 mixed logs from various services
    # Include many successful traces to hide the failure
    for i in range(20000):
        # Most traces are successful
        if random.random() < 0.95:
            all_logs.extend(generate_successful_trace())
        else:
            # Some random failures
            service = random.choice(services)
            trace_id = generate_trace_id()
            all_logs.append(
                generate_log_entry(
                    service, "ERROR", "Random service error", trace_id=trace_id
                )
            )

        # Add some noise logs without traces
        for _ in range(3):
            service = random.choice(services)
            all_logs.append(
                generate_log_entry(
                    service, "INFO", f"Health check passed for {service}"
                )
            )

    # Insert the specific failed order somewhere in the middle
    failed_trace_logs = generate_failed_trace_for_order_12345()
    insert_position = len(all_logs) // 2

    for i, log in enumerate(failed_trace_logs):
        all_logs.insert(insert_position + i * 100, log)  # Spread them out a bit

    # Shuffle to make it more realistic (but keep trace order logical)
    # Print all logs
    for log in all_logs:
        print(log)

    # Keep pod running
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
