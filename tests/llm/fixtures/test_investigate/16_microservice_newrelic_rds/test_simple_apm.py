#!/usr/bin/env python3

import os
import requests
import json
import base64

# Try with the secret token as an APM secret token (not API key)
APM_ENDPOINT = "https://test-9aa338.apm.us-central1.gcp.cloud.es.io"
SECRET_TOKEN = os.environ.get("ELASTIC_API_KEY")


def test_apm_info():
    """Test the APM server info endpoint"""
    print("=== Testing APM Server Info ===")
    
    try:
        response = requests.get(f"{APM_ENDPOINT}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_with_secret_token():
    """Test using the token as a secret token (not API key)"""
    print("\n=== Testing with Secret Token ===")
    
    # Simple APM event for testing
    event = {
        "metadata": {
            "service": {
                "name": "test-service", 
                "version": "1.0.0"
            }
        }
    }
    
    headers = {
        "Content-Type": "application/x-ndjson",
        "Authorization": f"Bearer {SECRET_TOKEN}"
    }
    
    # Convert to NDJSON format
    payload = json.dumps(event) + "\n"
    
    try:
        response = requests.post(
            f"{APM_ENDPOINT}/intake/v2/events",
            headers=headers,
            data=payload
        )
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        return response.status_code in [200, 202]
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_otlp_endpoint():
    """Test OTLP endpoint with different auth"""
    print("\n=== Testing OTLP Endpoint ===")
    
    trace_data = {
        "resourceSpans": [{
            "resource": {
                "attributes": [{"key": "service.name", "value": {"stringValue": "test"}}]
            },
            "scopeSpans": [{
                "spans": [{
                    "traceId": "12345678901234567890123456789012",
                    "spanId": "1234567890123456",
                    "name": "test-span",
                    "startTimeUnixNano": "1625097600000000000",
                    "endTimeUnixNano": "1625097601000000000"
                }]
            }]
        }]
    }
    
    # Try different auth headers
    auth_variants = [
        ("Authorization", f"Bearer {SECRET_TOKEN}"),
        ("Authorization", f"ApiKey {SECRET_TOKEN}"),
        ("elastic-apm-secret-token", SECRET_TOKEN),
    ]
    
    for header_name, header_value in auth_variants:
        print(f"\nTrying {header_name}: {header_value[:30]}...")
        
        headers = {
            "Content-Type": "application/json",
            header_name: header_value
        }
        
        try:
            response = requests.post(
                f"{APM_ENDPOINT}/v1/traces",
                headers=headers,
                json=trace_data
            )
            print(f"Status: {response.status_code}")
            if response.status_code != 401:
                print(f"Response: {response.text[:200]}")
                if response.status_code in [200, 202]:
                    return True
        except Exception as e:
            print(f"Error: {e}")
    
    return False

if __name__ == "__main__":
    print("Testing Elastic APM connectivity...")
    
    # Test basic connectivity
    if test_apm_info():
        print("✅ APM server is reachable")
    else:
        print("❌ APM server is not reachable")
    
    # Test secret token
    if test_with_secret_token():
        print("✅ Secret token works!")
    else:
        print("❌ Secret token failed")
    
    # Test OTLP
    if test_otlp_endpoint():
        print("✅ OTLP endpoint works!")
    else:
        print("❌ OTLP endpoint failed")