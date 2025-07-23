#!/bin/bash
# Environment Variables for HolmesGPT Enhanced MongoDB Toolset
# Source this file or add these to your deployment configuration

# InfraInsights Backend Configuration
export INFRAINSIGHTS_BACKEND_URL="http://k8s-ui-service.monitoring:5000"
export INFRAINSIGHTS_API_KEY="your-api-key-here"  # Optional

# HolmesGPT MongoDB Toolset Configuration
export HOLMESGPT_CONFIG_TOOLSETS='[
  {
    "name": "infrainsights_mongodb_enhanced",
    "description": "Enhanced MongoDB toolset with comprehensive monitoring",
    "enabled": true,
    "config": {
      "infrainsights_url": "'$INFRAINSIGHTS_BACKEND_URL'",
      "api_key": "'$INFRAINSIGHTS_API_KEY'",
      "timeout": 30,
      "enable_name_lookup": true,
      "use_v2_api": true
    }
  }
]'

# Alternative: Minimal configuration (uses defaults)
export HOLMESGPT_TOOLSETS_MINIMAL='[
  {
    "name": "infrainsights_mongodb_enhanced",
    "enabled": true,
    "config": {
      "infrainsights_url": "'$INFRAINSIGHTS_BACKEND_URL'"
    }
  }
]'

echo "✅ Environment variables set for HolmesGPT MongoDB toolset"
echo "🔧 InfraInsights URL: $INFRAINSIGHTS_BACKEND_URL"
echo "🔧 API Key configured: $([ -n "$INFRAINSIGHTS_API_KEY" ] && echo "Yes" || echo "No")" 