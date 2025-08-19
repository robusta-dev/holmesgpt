#!/usr/bin/env python3
"""
Test script for the HolmesGPT AlertManager Proxy.

This script is used for testing and development of the AlertManager proxy feature.
It sends test alerts to verify the proxy is working correctly.

To run this test:
1. Start the proxy in one terminal:
   holmes alertmanager-proxy serve --port 8080 --slack-webhook-url $SLACK_WEBHOOK

2. Run this script in another terminal:
   python scripts/test_alertmanager_proxy.py

3. Or use curl to send a test alert:
   curl -X POST http://localhost:8080/webhook \
     -H "Content-Type: application/json" \
     -d '{"alerts": [...]}'
"""

import json
import time
from datetime import datetime
import requests


def send_test_alert(url="http://localhost:8080/webhook"):
    """Send a test AlertManager webhook to the proxy."""

    # Example AlertManager webhook payload
    webhook_payload = {
        "receiver": "default",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighMemoryUsage",
                    "severity": "warning",
                    "namespace": "production",
                    "pod": "api-server-7b9c5d4f6-x2n4m",
                    "container": "api",
                    "cluster": "prod-cluster-1",
                },
                "annotations": {
                    "description": "Memory usage is above 90% for pod api-server-7b9c5d4f6-x2n4m",
                    "summary": "High memory usage detected",
                    "runbook_url": "https://docs.example.com/runbooks/high-memory",
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "generatorURL": "http://prometheus:9090/graph?g0.expr=container_memory_usage",
                "fingerprint": f"test-{int(time.time())}",
            },
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPUUsage",
                    "severity": "warning",
                    "namespace": "production",
                    "pod": "api-server-7b9c5d4f6-x2n4m",
                    "container": "api",
                    "cluster": "prod-cluster-1",
                },
                "annotations": {
                    "description": "CPU usage is above 80% for pod api-server-7b9c5d4f6-x2n4m",
                    "summary": "High CPU usage detected",
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "generatorURL": "http://prometheus:9090/graph?g0.expr=container_cpu_usage",
                "fingerprint": f"test-cpu-{int(time.time())}",
            },
        ],
        "groupLabels": {
            "namespace": "production",
            "pod": "api-server-7b9c5d4f6-x2n4m",
        },
        "commonLabels": {
            "namespace": "production",
            "cluster": "prod-cluster-1",
            "severity": "warning",
        },
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
        "version": "4",
        "groupKey": '{}:{namespace="production"}',
    }

    print(f"Sending test alert to {url}")
    print(f"Alert details: {len(webhook_payload['alerts'])} alerts")

    try:
        response = requests.post(
            url,
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("\n✅ Alert successfully processed and enriched!")
            print("Check your Slack channel for the enriched notification.")
        else:
            print(f"\n❌ Error: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to proxy. Make sure it's running:")
        print(
            "   holmes alertmanager-proxy serve --port 8080 --slack-webhook-url $SLACK_WEBHOOK"
        )
    except Exception as e:
        print(f"\n❌ Error sending alert: {e}")


def send_critical_alert(url="http://localhost:8080/webhook"):
    """Send a critical alert that might trigger investigation."""

    webhook_payload = {
        "receiver": "oncall",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "DatabaseDown",
                    "severity": "critical",
                    "namespace": "production",
                    "service": "postgres-primary",
                    "cluster": "prod-cluster-1",
                },
                "annotations": {
                    "description": "PostgreSQL primary database is not responding to health checks",
                    "summary": "Database connection failed",
                    "impact": "All services unable to write data",
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "generatorURL": "http://prometheus:9090/",
                "fingerprint": f"critical-{int(time.time())}",
            }
        ],
        "groupLabels": {"severity": "critical"},
        "commonLabels": {"severity": "critical", "namespace": "production"},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
        "version": "4",
        "groupKey": '{}:{severity="critical"}',
    }

    print(f"Sending CRITICAL alert to {url}")

    try:
        response = requests.post(
            url,
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {json.dumps(response.json(), indent=2)}")

    except Exception as e:
        print(f"Error: {e}")


def check_proxy_health(url="http://localhost:8080"):
    """Check if the proxy is running and healthy."""
    try:
        # Check health endpoint
        health_response = requests.get(f"{url}/health", timeout=5)
        print(f"Health check: {health_response.json()}")

        # Get stats
        stats_response = requests.get(f"{url}/stats", timeout=5)
        print(f"Proxy stats: {json.dumps(stats_response.json(), indent=2)}")

        # Get info
        info_response = requests.get(f"{url}/", timeout=5)
        print(f"Proxy info: {json.dumps(info_response.json(), indent=2)}")

        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys

    proxy_url = "http://localhost:8083"

    print("🔍 Checking proxy status...")
    if not check_proxy_health(proxy_url):
        print("\n❌ Proxy is not running. Start it with:")
        print(
            "   holmes alertmanager-proxy serve --port 8083 --slack-webhook-url $SLACK_WEBHOOK"
        )
        sys.exit(1)

    print("\n" + "=" * 50)
    print("📤 Sending test alerts...")
    print("=" * 50 + "\n")

    # Send regular warning alerts
    send_test_alert(f"{proxy_url}/webhook")

    print("\n" + "=" * 50)

    # Optionally send a critical alert
    if len(sys.argv) > 1 and sys.argv[1] == "--critical":
        print("📤 Sending CRITICAL alert...")
        print("=" * 50 + "\n")
        send_critical_alert(f"{proxy_url}/webhook")
