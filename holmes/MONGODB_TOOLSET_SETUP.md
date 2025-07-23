# 🚀 HolmesGPT Enhanced MongoDB Toolset Setup Guide

This guide explains how to enable and configure the Enhanced MongoDB Toolset in your HolmesGPT deployment.

## 📋 Prerequisites

1. **HolmesGPT** deployed and running
2. **InfraInsights Backend** accessible at your configured URL
3. **MongoDB instances** registered in InfraInsights with proper configuration
4. **pymongo** library available in HolmesGPT environment (will be auto-detected)

## 🔧 Configuration Methods

### Method 1: Configuration File (Recommended)

Create or update your `config.yaml`:

```yaml
toolsets:
  - name: "infrainsights_mongodb_enhanced"
    description: "Enhanced MongoDB toolset with comprehensive monitoring"
    enabled: true
    config:
      infrainsights_url: "http://k8s-ui-service.monitoring:5000"
      api_key: "${INFRAINSIGHTS_API_KEY}"  # Optional
      timeout: 30
      enable_name_lookup: true
      use_v2_api: true
```

Start HolmesGPT with:
```bash
holmes --config config.yaml
```

### Method 2: Environment Variables

```bash
# Set environment variables
export INFRAINSIGHTS_BACKEND_URL="http://k8s-ui-service.monitoring:5000"
export INFRAINSIGHTS_API_KEY="your-api-key"  # Optional

# Start HolmesGPT with toolset configuration
holmes --toolset infrainsights_mongodb_enhanced
```

### Method 3: Kubernetes Deployment

Apply the Kubernetes configuration:
```bash
kubectl apply -f examples/k8s-mongodb-toolset-config.yaml
```

### Method 4: Helm Chart

Add to your `values.yaml`:
```yaml
holmesgpt:
  toolsets:
    infrainsights_mongodb_enhanced:
      enabled: true
      config:
        infrainsights_url: "http://k8s-ui-service.monitoring:5000"
```

## 🔍 Verification

### 1. Check Toolset Loading

Look for these logs during HolmesGPT startup:
```
🔧 Loading enhanced MongoDB toolset: infrainsights_mongodb_enhanced
🚀🚀🚀 CREATING ENHANCED MONGODB TOOLSET 🚀🚀🚀
✅✅✅ ENHANCED MONGODB TOOLSET CREATED SUCCESSFULLY ✅✅✅
```

### 2. Verify Backend Connection

Check for successful health check:
```
🔍 Checking prerequisites for InfraInsights MongoDB client
✅ InfraInsights backend health check passed
```

### 3. Test Tool Availability

List available tools:
```bash
holmes --list-tools | grep mongodb
```

Expected output:
```
mongodb_health_check: Check MongoDB instance health and server status
mongodb_list_databases: List all databases with size information
mongodb_performance_metrics: Get comprehensive performance metrics
mongodb_slow_queries_analysis: Analyze slow queries and performance
mongodb_collection_stats: Get detailed collection statistics
mongodb_index_analysis: Analyze indexes and optimization opportunities
mongodb_replica_set_status: Check replica set status and configuration
mongodb_connection_analysis: Analyze connections and connection pool
mongodb_operations_analysis: Analyze current operations and statistics
mongodb_security_audit: Perform security audit and compliance check
mongodb_backup_analysis: Analyze backup status and strategies
mongodb_capacity_planning: Analyze capacity and growth projections
```

## 🎯 Usage Examples

### Basic Health Check
```bash
holmes "Check the health of MongoDB instance dock-atlantic-staging"
```

### Performance Investigation
```bash
holmes "Analyze performance issues in MongoDB dock-atlantic-staging database app_db"
```

### Index Optimization
```bash
holmes "Analyze indexes for collection users in database app_db on MongoDB dock-atlantic-staging"
```

### Capacity Planning
```bash
holmes "Provide capacity planning for MongoDB dock-atlantic-staging for the next 60 days"
```

## 🔧 Advanced Configuration

### Custom Timeout Settings
```yaml
config:
  infrainsights_url: "http://k8s-ui-service.monitoring:5000"
  timeout: 60  # Increase for slow networks
```

### Multiple Environment Support
```yaml
toolsets:
  - name: "infrainsights_mongodb_production"
    enabled: true
    config:
      infrainsights_url: "http://prod-infrainsights:5000"
      
  - name: "infrainsights_mongodb_staging"
    enabled: true
    config:
      infrainsights_url: "http://staging-infrainsights:5000"
```

### Debug Configuration
```yaml
config:
  infrainsights_url: "http://k8s-ui-service.monitoring:5000"
  timeout: 30
  enable_name_lookup: true
  use_v2_api: true
  debug: true  # Enable verbose logging
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. "InfraInsights client not available"
**Solution**: Check toolset configuration and ensure `infrainsights_url` is correct.

#### 2. "pymongo library not available"
**Solution**: Install pymongo in your HolmesGPT environment:
```bash
pip install pymongo
```

#### 3. "MongoDB instance 'name' not found"
**Solution**: Verify instance is registered in InfraInsights:
```bash
curl "http://k8s-ui-service.monitoring:5000/api/service-instances/mongodb/dock-atlantic-staging?includeConfig=true"
```

#### 4. "Failed to connect to MongoDB server - timeout"
**Solution**: Check MongoDB connection string and network connectivity.

### Debug Logging

Enable debug logging in your HolmesGPT configuration:
```yaml
logging:
  level: DEBUG
  loggers:
    "holmes.plugins.toolsets.infrainsights": DEBUG
```

## 📊 Available Tools Reference

| Tool | Purpose | Parameters |
|------|---------|------------|
| `mongodb_health_check` | Instance health monitoring | `instance_name` |
| `mongodb_list_databases` | Database inventory | `instance_name` |
| `mongodb_performance_metrics` | Performance analysis | `instance_name` |
| `mongodb_slow_queries_analysis` | Query optimization | `instance_name`, `database_name`, `slow_threshold_ms` |
| `mongodb_collection_stats` | Collection analysis | `instance_name`, `database_name`, `collection_name` |
| `mongodb_index_analysis` | Index optimization | `instance_name`, `database_name`, `collection_name` |
| `mongodb_replica_set_status` | Cluster monitoring | `instance_name` |
| `mongodb_connection_analysis` | Connection monitoring | `instance_name` |
| `mongodb_operations_analysis` | Operations monitoring | `instance_name`, `operation_threshold_ms` |
| `mongodb_security_audit` | Security compliance | `instance_name` |
| `mongodb_backup_analysis` | Backup verification | `instance_name` |
| `mongodb_capacity_planning` | Capacity planning | `instance_name`, `projection_days` |

## 🚀 Next Steps

1. **Configure your first MongoDB instance** in InfraInsights
2. **Test basic health check** with HolmesGPT
3. **Set up monitoring dashboards** using the toolset data
4. **Train your team** on available MongoDB analysis capabilities

## 📞 Support

- Check HolmesGPT logs for detailed error messages
- Verify InfraInsights backend connectivity
- Ensure MongoDB instances are properly configured with connection strings
- Validate PyMongo library availability

---

🎉 **You're all set!** Your HolmesGPT deployment now has comprehensive MongoDB monitoring and analysis capabilities! 