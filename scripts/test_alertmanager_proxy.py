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
    """Send a test AlertManager webhook to the proxy with mixed severity levels."""

    # Example AlertManager webhook payload with mixed severities
    webhook_payload = {
        "receiver": "default",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "InfoNotification",
                    "severity": "info",  # LOW SEVERITY - should be skipped by default
                    "namespace": "production",
                    "pod": "api-server-7b9c5d4f6-x2n4m",
                    "container": "api",
                    "cluster": "prod-cluster-1",
                },
                "annotations": {
                    "description": "Informational: New deployment version detected",
                    "summary": "Deployment updated to v2.3.1",
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "generatorURL": "http://prometheus:9090/",
                "fingerprint": f"test-info-{int(time.time())}",
            },
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighMemoryUsage",
                    "severity": "warning",  # HIGHER SEVERITY - should be enriched
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
                "fingerprint": f"test-memory-{int(time.time())}",
            },
            {
                "status": "firing",
                "labels": {
                    "alertname": "ServiceDown",
                    "severity": "critical",  # HIGHER SEVERITY - should be enriched
                    "namespace": "production",
                    "service": "payment-api",
                    "cluster": "prod-cluster-1",
                },
                "annotations": {
                    "description": "Payment API service is not responding to health checks",
                    "summary": "Critical service outage detected",
                    "impact": "Customers unable to complete transactions",
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "generatorURL": "http://prometheus:9090/graph?g0.expr=up",
                "fingerprint": f"test-critical-{int(time.time())}",
            },
        ],
        "groupLabels": {
            "namespace": "production",
        },
        "commonLabels": {
            "namespace": "production",
            "cluster": "prod-cluster-1",
        },
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
        "version": "4",
        "groupKey": '{}:{namespace="production"}',
    }

    print(f"Sending test alert to {url}")
    print(f"Alert details: {len(webhook_payload['alerts'])} alerts")
    print("  - 1 info alert (should be skipped by default severity filter)")
    print("  - 1 warning alert (should be enriched)")
    print("  - 1 critical alert (should be enriched)")

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
            response_data = response.json()
            print("\n✅ Alert successfully processed!")
            print(f"   Alerts received: {response_data.get('alerts_received', 0)}")
            print(f"   Alerts enriched: {response_data.get('alerts_enriched', 0)}")
            print("\n📊 Expected behavior based on severity filter:")
            print("   - Default (critical,warning): 2 alerts enriched, 1 skipped")
            print("   - Only critical: 1 alert enriched, 2 skipped")
            print("   - All severities: 3 alerts enriched, 0 skipped")
            print(
                "\nCheck your Slack channel or configured destinations for enriched notifications."
            )
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

    print("🚀 AlertManager Proxy Test Script")
    print("=" * 50)
    print("\n📝 To test the severity filter, start the proxy with:")
    print("\n   # Enrich only critical and warning alerts (default):")
    print("   holmes alertmanager-proxy serve --port 8083")
    print("\n   # Enrich only critical alerts:")
    print("   holmes alertmanager-proxy serve --port 8083 --severity critical")
    print("\n   # Enrich all severity levels:")
    print(
        "   holmes alertmanager-proxy serve --port 8083 --severity critical,warning,info"
    )
    print("\n" + "=" * 50)

    print("\n🔍 Checking proxy status...")
    if not check_proxy_health(proxy_url):
        print("\n❌ Proxy is not running. Start it with one of the commands above.")
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
