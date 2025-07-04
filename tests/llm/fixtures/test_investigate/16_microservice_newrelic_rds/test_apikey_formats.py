#!/usr/bin/env python3

import requests
import json
import base64
import os

# The API key in different formats
ENCODED_KEY = "cGRobjBKY0JVUlhNZkRXSGQ3bm86WmQ4Ymc0Z1Fpb0M1WDktbDZjNTVrZw=="
DECODED_KEY = base64.b64decode(ENCODED_KEY).decode()

APM_ENDPOINT = "https://test-9aa338.apm.us-central1.gcp.cloud.es.io"

def test_otlp_with_apikey():
    """Test OTLP with proper ApiKey format"""
    print("=== Testing OTLP with different ApiKey formats ===")
    
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
    
    # Test different authentication formats
    auth_tests = [
        ("ApiKey with base64", f"ApiKey {ENCODED_KEY}"),
        ("ApiKey with decoded", f"ApiKey {DECODED_KEY}"),
        ("Bearer with base64", f"Bearer {ENCODED_KEY}"),
        ("Bearer with decoded", f"Bearer {DECODED_KEY}"),
    ]
    
    for test_name, auth_header in auth_tests:
        print(f"\n--- {test_name} ---")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }
        
        try:
            response = requests.post(
                f"{APM_ENDPOINT}/v1/traces",
                headers=headers,
                json=trace_data,
                timeout=10
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
            if response.status_code in [200, 202]:
                print(f"✅ SUCCESS with {test_name}!")
                return auth_header
            elif response.status_code == 401:
                print(f"❌ Auth failed")
            else:
                print(f"❌ Status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return None

def test_elasticsearch_api():
    """Test if this is an Elasticsearch API key by trying ES endpoint"""
    print("\n=== Testing if this works as Elasticsearch API key ===")
    
    # Try Elasticsearch cluster info
    headers = {
        "Authorization": f"ApiKey {ENCODED_KEY}",
        "Content-Type": "application/json"
    }
    
    # Try to access cluster through the es endpoint
    es_url = "https://test-9aa338.es.us-central1.gcp.cloud.es.io"
    
    try:
        response = requests.get(f"{es_url}/", headers=headers, timeout=10)
        print(f"ES Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ This API key works for Elasticsearch!")
            cluster_info = response.json()
            print(f"Cluster: {cluster_info.get('cluster_name', 'unknown')}")
            return True
    except Exception as e:
        print(f"ES Error: {e}")
    
    return False

if __name__ == "__main__":
    print(f"Testing API Key: {DECODED_KEY}")
    print(f"Encoded: {ENCODED_KEY}")
    
    # Test OTLP endpoint
    success_auth = test_otlp_with_apikey()
    
    # Test as ES API key
    es_works = test_elasticsearch_api()
    
    print("\n=== Summary ===")
    if success_auth:
        print(f"✅ OTLP works with: {success_auth}")
    elif es_works:
        print("✅ This is a valid Elasticsearch API key but doesn't work for APM OTLP")
        print("   You may need to create an APM-specific secret token instead")
    else:
        print("❌ API key doesn't work for OTLP or Elasticsearch")
        print("   Check the key permissions or create an APM secret token")