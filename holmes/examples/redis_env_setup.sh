#!/bin/bash

# Redis Toolset Environment Setup Script
# This script sets up environment variables for the InfraInsights Redis toolset

echo "🚀 Setting up InfraInsights Redis Toolset Environment Variables"

# Required: InfraInsights backend URL
export INFRAINSIGHTS_URL="http://k8s-ui-service.monitoring:5000"

# Optional: API key for authenticated access
# export INFRAINSIGHTS_API_KEY="your-api-key-here"

# Optional: Connection timeout (default: 30 seconds)
export INFRAINSIGHTS_TIMEOUT="30"

# Optional: Enable instance name lookup (default: true)
export INFRAINSIGHTS_ENABLE_NAME_LOOKUP="true"

# Optional: Use v2 API (default: true)
export INFRAINSIGHTS_USE_V2_API="true"

# Redis-specific configurations
export REDIS_DEFAULT_PORT="6379"
export REDIS_CONNECTION_TIMEOUT="30"

# Alternative configurations for different environments
case "${ENVIRONMENT:-production}" in
  "development")
    export INFRAINSIGHTS_URL="http://localhost:3000"
    export INFRAINSIGHTS_TIMEOUT="15"
    echo "✅ Development environment configured"
    ;;
  "staging")
    export INFRAINSIGHTS_URL="http://k8s-ui-service.staging:5000"
    export INFRAINSIGHTS_TIMEOUT="30"
    echo "✅ Staging environment configured"
    ;;
  "production")
    export INFRAINSIGHTS_URL="http://k8s-ui-service.production:5000"
    export INFRAINSIGHTS_TIMEOUT="45"
    echo "✅ Production environment configured"
    ;;
  *)
    echo "✅ Default production environment configured"
    ;;
esac

# Validate required variables
if [ -z "$INFRAINSIGHTS_URL" ]; then
    echo "❌ Error: INFRAINSIGHTS_URL is required"
    exit 1
fi

echo "📋 Environment Variables Summary:"
echo "   INFRAINSIGHTS_URL: $INFRAINSIGHTS_URL"
echo "   INFRAINSIGHTS_TIMEOUT: $INFRAINSIGHTS_TIMEOUT"
echo "   INFRAINSIGHTS_ENABLE_NAME_LOOKUP: $INFRAINSIGHTS_ENABLE_NAME_LOOKUP"
echo "   INFRAINSIGHTS_USE_V2_API: $INFRAINSIGHTS_USE_V2_API"
echo "   REDIS_DEFAULT_PORT: $REDIS_DEFAULT_PORT"

# Install required Python dependencies
echo "🔧 Installing Redis Python dependencies..."
pip install redis>=4.0.0

echo "✅ InfraInsights Redis Toolset environment setup complete!"
echo ""
echo "🎯 Usage Examples:"
echo "   holmes 'Check Redis health for consolidated-demo-prod'"
echo "   holmes 'Analyze Redis memory usage for consolidated-demo-prod'"
echo "   holmes 'Check Redis performance metrics for consolidated-demo-prod'"
echo "   holmes 'Perform Redis security audit for consolidated-demo-prod'"
echo ""
echo "📝 Configuration file example: holmes/examples/infrainsights_redis_config.yaml"
echo "📚 Full documentation: holmes/REDIS_TOOLSET_SETUP.md" 