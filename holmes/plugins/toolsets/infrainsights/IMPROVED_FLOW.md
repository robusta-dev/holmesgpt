# InfraInsights Toolsets - Improved Flow Documentation

## Overview

The InfraInsights toolsets have been improved to handle connectivity and configuration issues more gracefully. The new flow eliminates the need for active instances during initialization and provides better error handling and user guidance.

## Key Improvements

### 1. **Lazy Loading & Connection Handling**

**Before:**
- Toolsets tried to connect to InfraInsights API during HolmesGPT startup
- Failed if API was not accessible or no instances were configured
- Showed generic error messages

**After:**
- Toolsets only validate configuration during startup (no network calls)
- API connections are made lazily when tools are actually invoked
- Graceful degradation with helpful error messages

### 2. **Smart Instance Discovery**

The improved flow follows this intelligent sequence:

```
User Query: "Check the health of my production Elasticsearch cluster"
    ↓
1. Parse Intent: HolmesGPT identifies this needs Elasticsearch toolset
    ↓
2. Tool Invocation: Elasticsearch tool is called
    ↓
3. Instance Selection Algorithm:
   a) Check for explicit instance_id parameter
   b) Check for explicit instance_name parameter  
   c) Analyze prompt for keywords (production, staging, etc.)
   d) Check user's current context/preference
   e) Fallback to first available active instance
    ↓
4. API Connection: Connect to InfraInsights API (only when needed)
    ↓
5. Instance Discovery: Fetch available instances and credentials
    ↓
6. Service Connection: Connect to actual service (Elasticsearch)
    ↓
7. Investigation: Execute the requested operation
    ↓
8. Response: Return results or helpful error guidance
```

### 3. **Enhanced Error Handling**

Each error scenario now provides specific guidance:

#### **API Connectivity Issues**
```
Investigation failed for elasticsearch service: Connection refused

🔍 Troubleshooting Steps:

1. Check InfraInsights API Status
   - URL: http://k8s-ui-service.monitoring:5000
   - Try accessing the InfraInsights dashboard to verify it's running

2. Verify Service Instance Configuration
   - Ensure elasticsearch instances are properly configured in InfraInsights
   - Check that instances are in 'active' status

3. Authentication Issues
   - Verify your API key/credentials are correct and not expired
   - Check user permissions for elasticsearch access

4. Network Connectivity
   - Ensure HolmesGPT can reach the InfraInsights API URL
   - Check firewall/proxy settings if applicable

5. Instance Context
   - Try specifying an instance explicitly: "Check the production elasticsearch cluster"
   - Set your user context for elasticsearch in InfraInsights

💡 Quick Test: Access InfraInsights dashboard and verify elasticsearch instances are visible and accessible.
```

#### **No Instances Available**
```
No elasticsearch instance available or specified.

Possible solutions:
1. Ensure InfraInsights API is accessible at the configured URL
2. Check that elasticsearch instances are configured in InfraInsights  
3. Verify authentication credentials are correct
4. Specify instance explicitly using 'instance_id' or 'instance_name' parameter
5. Set user context for elasticsearch service type

Debug: Check InfraInsights dashboard for available elasticsearch instances.
```

### 4. **Diagnostic Tool**

A new diagnostic tool provides comprehensive health checking:

```yaml
# Usage examples:
"Run InfraInsights diagnostic"
"Check InfraInsights connectivity"  
"Show available service instances"
"Diagnose elasticsearch connectivity"
```

**Output includes:**
- API connectivity status
- Authentication configuration
- Available instances by service type
- Specific recommendations for issues
- Detailed instance information (optional)

## Configuration Changes

### **Startup Prerequisites**

**Before:**
```python
def prerequisites_callable(self, config):
    # Makes network call during startup
    client = InfraInsightsClient(config)
    if not client.health_check():
        return False, "InfraInsights API is not accessible"
    # ... more network calls
```

**After:**
```python
def prerequisites_callable(self, config):
    # Only validates configuration format
    if not config.get('infrainsights_url'):
        return False, "InfraInsights URL is required"
    if not (has_api_key or has_credentials):
        return False, "Authentication required"
    return True, "Configuration validated"
```

### **Tool Invocation**

**Before:**
```python
def _invoke(self, params):
    try:
        instance = self.get_instance_from_params(params)
        # ... rest of logic
    except Exception as e:
        return StructuredToolResult(
            status=ToolResultStatus.ERROR,
            error=f"Failed: {str(e)}"
        )
```

**After:**
```python
def _invoke(self, params):
    try:
        instance = self.get_instance_from_params(params)
        # ... rest of logic
    except Exception as e:
        error_msg = f"Failed: {str(e)}"
        helpful_msg = self.get_helpful_error_message(error_msg)
        return StructuredToolResult(
            status=ToolResultStatus.ERROR,
            error=helpful_msg
        )
```

## Usage Patterns

### **1. Normal Investigation (API Accessible)**

```
User: "List all indices in my production Elasticsearch cluster"

Flow:
1. HolmesGPT identifies Elasticsearch toolset needed
2. Tool analyzes prompt: "production" → looks for production instances
3. Connects to InfraInsights API
4. Finds production Elasticsearch instance
5. Gets credentials for that instance
6. Connects to Elasticsearch
7. Lists indices
8. Returns results
```

### **2. API Not Accessible**

```
User: "Check Kafka consumer lag"

Flow:  
1. HolmesGPT identifies Kafka toolset needed
2. Tool tries to connect to InfraInsights API
3. Connection fails
4. Returns helpful error message with troubleshooting steps
5. User can fix connectivity and retry
```

### **3. No Instances Configured**

```
User: "Show MongoDB databases"

Flow:
1. HolmesGPT identifies MongoDB toolset needed  
2. Tool connects to InfraInsights API successfully
3. No MongoDB instances found
4. Returns guidance on configuring MongoDB instances
5. User can configure instances and retry
```

### **4. Diagnostic Mode**

```
User: "Why aren't my InfraInsights toolsets working?"

Flow:
1. HolmesGPT suggests diagnostic tool
2. Diagnostic tool checks all service types
3. Reports connectivity, authentication, and instance status
4. Provides specific recommendations
5. User can address issues and retry
```

## Benefits

### **For Users:**
- ✅ HolmesGPT starts successfully even when InfraInsights is down
- ✅ Clear, actionable error messages instead of technical failures
- ✅ Diagnostic tools to understand current state
- ✅ Intelligent instance selection from natural language

### **For Operators:**
- ✅ No startup failures due to temporary connectivity issues
- ✅ Easier troubleshooting with detailed error information
- ✅ Gradual service discovery (toolsets work as services come online)
- ✅ Better logging and monitoring of connectivity issues

### **For Development:**
- ✅ Easier testing (can start HolmesGPT without full InfraInsights setup)
- ✅ Graceful degradation in various failure scenarios
- ✅ Modular error handling that can be extended
- ✅ Clear separation between configuration and runtime connectivity

## Implementation Details

### **Key Files Modified:**

1. **`base_toolset.py`**
   - `prerequisites_callable()` - No network calls during startup
   - `get_available_instances()` - Graceful error handling
   - `get_instance_from_params()` - Better error messages
   - `get_helpful_error_message()` - User-friendly error guidance

2. **`infrainsights_client.py`**
   - `get_service_instance_summary()` - Diagnostic information
   - Enhanced error handling throughout

3. **`elasticsearch_toolset.py`** (and other service toolsets)
   - Improved error handling in `_invoke()` methods
   - Use of helpful error messages

4. **`diagnostic_tool.py`** (new)
   - Comprehensive diagnostic capabilities
   - Health checking and troubleshooting guidance

### **Configuration Requirements:**

**Minimum Required:**
```yaml
infrainsights_url: "http://k8s-ui-service.monitoring:5000"
api_key: "your-jwt-token"  # OR username/password
```

**Optional:**
```yaml
timeout: 30
username: "your-username"  # Alternative to api_key
password: "your-password"  # Alternative to api_key
```

## Migration Guide

If you have existing HolmesGPT + InfraInsights setups:

1. **Update toolsets** to the new versions
2. **Test startup** - should now succeed even if InfraInsights is down
3. **Use diagnostic tool** to verify connectivity: `"Run InfraInsights diagnostic"`
4. **Test investigation queries** with various scenarios
5. **Monitor logs** for improved error messages and guidance

## Future Enhancements

1. **Instance Caching** - Cache available instances to reduce API calls
2. **Health Monitoring** - Periodic health checks with status reporting
3. **Auto-Retry Logic** - Automatic retry on transient failures
4. **User Preferences** - Remember user's preferred instances per service type
5. **Bulk Operations** - Tools that work across multiple instances simultaneously 