#!/usr/bin/env python3

import os
import requests
import time
import uuid

# Configuration
APM_ENDPOINT = "https://test-9aa338.apm.us-central1.gcp.cloud.es.io/v1/traces"
SECRET_TOKEN = os.environ.get("ELASTIC_API_KEY")


def generate_test_trace():
    """Generate a simple test trace in OTLP format"""
    trace_id = uuid.uuid4().hex[:32]
    span_id = uuid.uuid4().hex[:16]
    now_ns = int(time.time() * 1e9)

    trace_data = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "test-service"},
                        },
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "test-tracer", "version": "1.0.0"},
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": "test-operation",
                                "kind": 1,  # SPAN_KIND_INTERNAL
                                "startTimeUnixNano": str(
                                    now_ns - 1000000000
                                ),  # 1 second ago
                                "endTimeUnixNano": str(now_ns),
                                "attributes": [
                                    {
                                        "key": "http.method",
                                        "value": {"stringValue": "GET"},
                                    },
                                    {
                                        "key": "http.url",
                                        "value": {
                                            "stringValue": "http://test-service/api/test"
                                        },
                                    },
                                    {
                                        "key": "http.status_code",
                                        "value": {"intValue": "200"},
                                    },
                                ],
                                "status": {
                                    "code": 1  # STATUS_CODE_OK
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }
    return trace_data


def test_apm_auth_methods():
    """Test different authentication methods"""
    trace_data = generate_test_trace()

    auth_methods = [
        ("Bearer", f"Bearer {SECRET_TOKEN}"),
        ("ApiKey", f"ApiKey {SECRET_TOKEN}"),
        ("Simple", SECRET_TOKEN),
    ]

    for method_name, auth_header in auth_methods:
        print(f"\n=== Testing {method_name} authentication ===")

        headers = {"Content-Type": "application/json", "Authorization": auth_header}

        try:
            response = requests.post(
                APM_ENDPOINT, headers=headers, json=trace_data, timeout=10
            )

            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Body: {response.text[:500]}...")

            if response.status_code == 200:
                print(f"✅ SUCCESS with {method_name} authentication!")
                return method_name
            elif response.status_code == 401:
                print(f"❌ Authentication failed with {method_name}")
            elif response.status_code == 404:
                print("❌ Endpoint not found - check URL")
            else:
                print(f"❌ Unexpected status: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")

    return None


def test_alternative_endpoints():
    """Test different endpoint variations"""
    endpoints = [
        "https://test-9aa338.apm.us-central1.gcp.cloud.es.io/v1/traces",
        "https://test-9aa338.apm.us-central1.gcp.cloud.es.io/intake/v2/events",
        "https://test-9aa338.apm.us-central1.gcp.cloud.es.io/",
        "https://test-9aa338.apm.us-central1.gcp.cloud.es.io/intake/v2/traces",
    ]

    trace_data = generate_test_trace()

    for endpoint in endpoints:
        print(f"\n=== Testing endpoint: {endpoint} ===")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SECRET_TOKEN}",
        }

        try:
            response = requests.post(
                endpoint, headers=headers, json=trace_data, timeout=10
            )

            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:200]}...")

            if response.status_code in [200, 202]:
                print(f"✅ SUCCESS with endpoint: {endpoint}")
                return endpoint

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")

    return None


if __name__ == "__main__":
    print("Testing Elastic APM trace upload...")
    print(f"APM Endpoint: {APM_ENDPOINT}")
    print(f"Secret Token: {SECRET_TOKEN[:20]}...")

    # Test authentication methods
    successful_auth = test_apm_auth_methods()

    if not successful_auth:
        print("\n=== Trying alternative endpoints ===")
        successful_endpoint = test_alternative_endpoints()

    print("\n=== Summary ===")
    if successful_auth:
        print(
            f"✅ Traces can be uploaded successfully using {successful_auth} authentication"
        )
    else:
        print("❌ No authentication method worked - check API key and endpoint")
