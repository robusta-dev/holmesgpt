#!/usr/bin/env python3
"""
Test script for the Generic Toolsets + InfraInsights Plugin architecture

This script tests the complete flow:
1. Smart Router parsing prompts
2. InfraInsights Plugin resolving instances
3. Generic toolsets working with environment variables
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the holmes directory to Python path for imports
holmes_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, holmes_dir)

def test_smart_router():
    """Test the Smart Router's prompt parsing capabilities"""
    print("\n" + "="*60)
    print("🧠 TESTING SMART ROUTER")
    print("="*60)
    
    try:
        from smart_router import parse_prompt_for_routing
        
        test_prompts = [
            "Check the health of my dock-atlantic-staging Elasticsearch cluster and list all indices",
            "Show me Kafka topics in production environment",
            "Get MongoDB database statistics for development instance",
            "List Redis keys in staging cache",
            "Check Kubernetes pods in prod-cluster"
        ]
        
        for prompt in test_prompts:
            print(f"\n📝 Testing prompt: '{prompt}'")
            
            route_info = parse_prompt_for_routing(prompt)
            
            print(f"   🎯 Service Type: {route_info.service_type}")
            print(f"   🏷️  Instance Hint: {route_info.instance_hint}")
            print(f"   📊 Confidence: {route_info.confidence:.2f}")
            print(f"   🔍 Method: {route_info.extraction_method}")
            print(f"   🔤 Keywords: {route_info.detected_keywords}")
            
            # Validate results
            if route_info.service_type and route_info.instance_hint:
                print("   ✅ PASS: Service and instance detected")
            elif route_info.service_type:
                print("   ⚠️  PARTIAL: Service detected, no instance hint")
            else:
                print("   ❌ FAIL: No service detected")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_infrainsights_plugin():
    """Test the InfraInsights Plugin (mock mode)"""
    print("\n" + "="*60)
    print("🔌 TESTING INFRAINSIGHTS PLUGIN")
    print("="*60)
    
    try:
        # Create a mock configuration
        mock_config = {
            'infrainsights_url': 'http://localhost:3000',
            'api_key': 'mock-api-key',
            'timeout': 30
        }
        
        # Since we don't have actual InfraInsights running, we'll test the structure
        from infrainsights_plugin import InfraInsightsPlugin, InstanceResolutionResult
        
        # Test plugin initialization
        plugin = InfraInsightsPlugin(mock_config)
        print("✅ Plugin initialized successfully")
        
        # Test diagnostic info
        diagnostic = plugin.get_diagnostic_info()
        print(f"📊 Diagnostic info: {json.dumps(diagnostic, indent=2)}")
        
        # Test environment variable setting (mock)
        print("\n🔧 Testing environment variable setting:")
        
        # Mock instance object
        class MockInstance:
            def __init__(self, name, environment):
                self.name = name
                self.environment = environment
                self.id = f"mock-{name}"
                self.status = "active"
                self.connection_details = {
                    'url': f'http://mock-{name}.example.com:9200',
                    'username': 'mock_user',
                    'password': 'mock_pass'
                }
        
        mock_instance = MockInstance("dock-atlantic-staging", "staging")
        
        # Test environment setting
        plugin._set_toolset_environment('elasticsearch', mock_instance)
        
        # Check if environment variables were set
        es_url = os.getenv('ELASTICSEARCH_URL')
        es_user = os.getenv('ELASTICSEARCH_USERNAME')
        current_instance = os.getenv('CURRENT_INSTANCE_NAME')
        
        print(f"   ELASTICSEARCH_URL: {es_url}")
        print(f"   ELASTICSEARCH_USERNAME: {es_user}")
        print(f"   CURRENT_INSTANCE_NAME: {current_instance}")
        
        if es_url and current_instance == "dock-atlantic-staging":
            print("✅ Environment variables set correctly")
            return True
        else:
            print("❌ Environment variables not set correctly")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_generic_elasticsearch_toolset():
    """Test the generic Elasticsearch toolset (mock mode)"""
    print("\n" + "="*60)
    print("⚡ TESTING GENERIC ELASTICSEARCH TOOLSET")
    print("="*60)
    
    try:
        # Set up mock environment variables
        os.environ['ELASTICSEARCH_URL'] = 'http://mock-elasticsearch:9200'
        os.environ['ELASTICSEARCH_USERNAME'] = 'mock_user'
        os.environ['ELASTICSEARCH_PASSWORD'] = 'mock_pass'
        os.environ['CURRENT_INSTANCE_NAME'] = 'dock-atlantic-staging'
        os.environ['CURRENT_INSTANCE_ENVIRONMENT'] = 'staging'
        
        from generic_elasticsearch import BaseElasticsearchTool
        
        # Test base functionality
        tool = BaseElasticsearchTool()
        
        # Test instance info retrieval
        instance_info = tool._get_instance_info()
        print(f"📋 Instance info: {json.dumps(instance_info, indent=2)}")
        
        if instance_info['name'] == 'dock-atlantic-staging':
            print("✅ Instance info retrieved correctly")
        else:
            print("❌ Instance info not correct")
            
        # Test ensure instance resolved
        mock_params = {'prompt': 'Check elasticsearch health'}
        resolved = tool._ensure_instance_resolved(mock_params, 'Check elasticsearch health')
        
        if resolved:
            print("✅ Instance resolution check passed")
            return True
        else:
            print("❌ Instance resolution check failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_integration_flow():
    """Test the complete integration flow"""
    print("\n" + "="*60)
    print("🔗 TESTING COMPLETE INTEGRATION FLOW")
    print("="*60)
    
    try:
        from infrainsights_integration import test_integration
        
        test_prompt = "Check the health of my dock-atlantic-staging Elasticsearch cluster and list all indices"
        
        print(f"📝 Testing with prompt: '{test_prompt}'")
        
        # Run the integration test
        result = test_integration(test_prompt)
        
        print(f"📊 Integration test result:")
        print(json.dumps(result, indent=2))
        
        # Check if routing worked
        route_info = result.get('route_info', {})
        if route_info.get('service_type') == 'elasticsearch' and route_info.get('instance_hint'):
            print("✅ Routing successful")
            return True
        else:
            print("❌ Routing failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def run_all_tests():
    """Run all tests and provide summary"""
    print("🚀 STARTING GENERIC TOOLSETS + INFRAINSIGHTS PLUGIN TESTS")
    print("=" * 80)
    
    tests = [
        ("Smart Router", test_smart_router),
        ("InfraInsights Plugin", test_infrainsights_plugin),
        ("Generic Elasticsearch Toolset", test_generic_elasticsearch_toolset),
        ("Integration Flow", test_integration_flow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n📈 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! The architecture is ready for implementation.")
    else:
        print("⚠️ Some tests failed. Check the issues above before proceeding.")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 