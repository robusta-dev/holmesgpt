# InfraInsights Redis Toolset Setup Guide

## 🚀 Overview

The InfraInsights Redis Toolset provides comprehensive monitoring, analysis, and troubleshooting capabilities for Redis instances managed through the InfraInsights platform. This toolset enables HolmesGPT to perform deep Redis analysis including performance monitoring, memory optimization, security audits, and capacity planning.

## 📋 Features

### 🔍 **Health & Monitoring Tools**
- **Redis Health Check** - Server information, connectivity, and basic statistics
- **Performance Metrics** - Operations per second, hit ratios, memory efficiency
- **Connection Analysis** - Client connections, connection pools, and usage patterns

### 🧠 **Memory & Optimization Tools**  
- **Memory Analysis** - Memory usage, fragmentation analysis, and optimization recommendations
- **Key Analysis** - Key patterns, types, sizes, and TTL distribution
- **Configuration Analysis** - Configuration review and optimization opportunities

### ⚡ **Performance & Troubleshooting Tools**
- **Slow Log Analysis** - Identify performance bottlenecks and slow commands
- **Capacity Planning** - Growth projections and resource planning

### 🔒 **High Availability & Security Tools**
- **Replication Status** - Master-slave health and replication lag monitoring
- **Cluster Analysis** - Redis Cluster status, node health, and slot distribution
- **Persistence Analysis** - RDB/AOF configuration and backup status
- **Security Audit** - Authentication, ACL, and security best practices

## 🛠️ Prerequisites

### 1. Python Dependencies
```bash
pip install redis>=4.0.0
```

### 2. InfraInsights Backend
- Running InfraInsights backend with Redis service instances
- API access to retrieve Redis instance configurations
- Redis instances with connection details (host, port, password)

### 3. Network Connectivity
- HolmesGPT can reach InfraInsights backend API
- HolmesGPT can connect to Redis instances via network

## 📦 Installation & Configuration

### Method 1: YAML Configuration File

Create `config.yaml`:
```yaml
toolsets:
  infrainsights_redis:
    enabled: true
    config:
      infrainsights_url: "http://k8s-ui-service.monitoring:5000"
      api_key: "your-api-key-here"  # Optional
      timeout: 30
      enable_name_lookup: true
      use_v2_api: true
```

### Method 2: Environment Variables

```bash
# Set up environment variables
export INFRAINSIGHTS_URL="http://k8s-ui-service.monitoring:5000"
export INFRAINSIGHTS_API_KEY="your-api-key-here"  # Optional
export INFRAINSIGHTS_TIMEOUT="30"
export INFRAINSIGHTS_ENABLE_NAME_LOOKUP="true"
export INFRAINSIGHTS_USE_V2_API="true"

# Use the setup script
source holmes/examples/redis_env_setup.sh
```

### Method 3: Kubernetes Deployment

```bash
# Apply Kubernetes configuration
kubectl apply -f holmes/examples/k8s-redis-toolset-config.yaml

# Verify deployment
kubectl get pods -n monitoring -l component=redis-toolset
```

### Method 4: Helm Chart Values

```yaml
# values.yaml
infrainsights:
  redis:
    enabled: true
    config:
      url: "http://k8s-ui-service.monitoring:5000"
      timeout: 30
      enableNameLookup: true
      useV2Api: true
```

## 🎯 Usage Examples

### Basic Health Checks
```bash
# Basic health check
holmes "Check the health of Redis instance consolidated-demo-prod"

# Comprehensive health assessment  
holmes "Investigate any issues with Redis consolidated-demo-prod and provide a complete health assessment"
```

### Performance Analysis
```bash
# Performance metrics analysis
holmes "Analyze performance metrics for Redis consolidated-demo-prod"

# Memory usage analysis
holmes "Analyze memory usage and fragmentation for Redis consolidated-demo-prod"

# Slow query analysis
holmes "Find and analyze slow commands in Redis consolidated-demo-prod"
```

### Operational Analysis
```bash
# Connection analysis
holmes "Analyze connections and client usage for Redis consolidated-demo-prod"

# Configuration review
holmes "Review Redis configuration for consolidated-demo-prod and provide optimization recommendations"

# Capacity planning
holmes "Provide capacity planning analysis for Redis consolidated-demo-prod for the next 60 days"
```

### Security & Compliance
```bash
# Security audit
holmes "Perform a security audit on Redis consolidated-demo-prod"

# Replication health (for clustered Redis)
holmes "Check replication status and master-slave health for Redis consolidated-demo-prod"
```

### Advanced Troubleshooting
```bash
# Comprehensive investigation
holmes "Redis consolidated-demo-prod has been experiencing performance issues. Perform a comprehensive analysis including memory usage, slow log analysis, connection patterns, and configuration optimization recommendations"

# Memory optimization deep dive
holmes "The Redis instance consolidated-demo-prod is using high memory. Analyze memory fragmentation, key patterns, and provide optimization strategies"
```

## 🔧 Configuration Reference

### Core Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `infrainsights_url` | string | required | InfraInsights backend URL |
| `api_key` | string | optional | API key for authentication |
| `timeout` | integer | 30 | Connection timeout in seconds |
| `enable_name_lookup` | boolean | true | Enable instance name lookups |
| `use_v2_api` | boolean | true | Use v2 API endpoints |

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INFRAINSIGHTS_URL` | Backend URL | `http://k8s-ui-service.monitoring:5000` |
| `INFRAINSIGHTS_API_KEY` | Authentication key | `your-api-key-here` |
| `INFRAINSIGHTS_TIMEOUT` | Connection timeout | `30` |
| `INFRAINSIGHTS_ENABLE_NAME_LOOKUP` | Enable name lookup | `true` |
| `INFRAINSIGHTS_USE_V2_API` | Use v2 API | `true` |

## 🔍 Available Tools

### 1. `redis_health_check`
**Purpose**: Check Redis instance health and server information  
**Parameters**: `instance_name` (required)  
**Output**: Connection status, server info, memory stats, database info

### 2. `redis_performance_metrics`
**Purpose**: Get comprehensive performance metrics and statistics  
**Parameters**: `instance_name` (required)  
**Output**: Hit ratios, operations/sec, memory metrics, connection stats

### 3. `redis_memory_analysis`
**Purpose**: Analyze memory usage, fragmentation, and optimization opportunities  
**Parameters**: `instance_name` (required)  
**Output**: Memory breakdown, fragmentation analysis, optimization recommendations

### 4. `redis_key_analysis`
**Purpose**: Analyze key patterns, types, and key space distribution  
**Parameters**: `instance_name` (required), `database_id` (optional), `pattern` (optional), `sample_size` (optional)  
**Output**: Key statistics, type distribution, pattern analysis, large keys

### 5. `redis_slow_log_analysis`
**Purpose**: Analyze slow log for performance bottlenecks  
**Parameters**: `instance_name` (required), `max_entries` (optional)  
**Output**: Slow commands, execution times, frequency analysis, recommendations

### 6. `redis_connection_analysis`
**Purpose**: Analyze connections and client statistics  
**Parameters**: `instance_name` (required)  
**Output**: Connection overview, client analysis, connection patterns

### 7. `redis_replication_status`
**Purpose**: Check replication status and master-slave health  
**Parameters**: `instance_name` (required)  
**Output**: Replication role, master/slave info, replication health

### 8. `redis_persistence_analysis`
**Purpose**: Analyze persistence configuration and backup status  
**Parameters**: `instance_name` (required)  
**Output**: RDB/AOF configuration, backup status, data safety analysis

### 9. `redis_cluster_analysis`
**Purpose**: Analyze Redis Cluster status and node health  
**Parameters**: `instance_name` (required)  
**Output**: Cluster status, node details, slot distribution, health summary

### 10. `redis_security_audit`
**Purpose**: Perform security audit and configuration analysis  
**Parameters**: `instance_name` (required)  
**Output**: Authentication status, access control, security recommendations

### 11. `redis_capacity_planning`
**Purpose**: Analyze capacity and provide growth projections  
**Parameters**: `instance_name` (required), `projection_days` (optional)  
**Output**: Current usage, growth projections, capacity recommendations

### 12. `redis_configuration_analysis`
**Purpose**: Analyze configuration and optimization opportunities  
**Parameters**: `instance_name` (required)  
**Output**: Configuration categories, optimization analysis, configuration scores

## 🧪 Testing the Setup

### 1. Verify Toolset Loading
```bash
holmes --list-toolsets | grep redis
```
Expected output: `infrainsights_redis_enhanced`

### 2. Test Basic Connectivity
```bash
holmes "List all available Redis instances"
```

### 3. Test Health Check
```bash
holmes "Check health of Redis instance consolidated-demo-prod"
```

### 4. Verify Tool Functionality
```bash
holmes "What Redis analysis tools are available?"
```

## 🚨 Troubleshooting

### Common Issues

#### 1. **Toolset Not Loading**
```
Error: infrainsights_redis_enhanced toolset not found
```

**Solutions**:
- Verify configuration file path and syntax
- Check environment variables are set correctly
- Ensure the toolset is enabled in configuration
- Review HolmesGPT logs for detailed error messages

#### 2. **InfraInsights Connection Failed**
```
Error: InfraInsights backend at http://... is not accessible
```

**Solutions**:
- Verify InfraInsights backend URL is correct and reachable
- Check network connectivity between HolmesGPT and InfraInsights
- Validate API key if authentication is required
- Test manual curl request to verify backend availability

#### 3. **Redis Connection Timeout**
```
Error: Redis connection timeout
```

**Solutions**:
- Verify Redis instance host and port are correct
- Check network connectivity between HolmesGPT and Redis instances
- Validate Redis password in instance configuration
- Increase connection timeout in configuration

#### 4. **Authentication Error**
```
Error: Redis authentication failed - check password
```

**Solutions**:
- Verify Redis password in InfraInsights instance configuration
- Check if Redis requires authentication (requirepass setting)
- Ensure password is correctly stored and retrieved from InfraInsights

#### 5. **Missing Dependencies**
```
Error: redis library not available. Please install: pip install redis
```

**Solutions**:
- Install Redis Python library: `pip install redis>=4.0.0`
- Verify virtual environment has correct dependencies
- Check requirements.txt includes redis dependency

### Debug Mode

Enable debug logging for detailed troubleshooting:
```bash
export HOLMES_LOG_LEVEL="DEBUG"
holmes "Check Redis health for consolidated-demo-prod"
```

### Manual Testing

Test InfraInsights API manually:
```bash
# Test backend connectivity
curl -X GET "http://k8s-ui-service.monitoring:5000/api/health"

# Test Redis instance retrieval
curl -X GET "http://k8s-ui-service.monitoring:5000/api/service-instances/redis/consolidated-demo-prod?includeConfig=true"
```

Test Redis connectivity manually:
```bash
# Using redis-cli
redis-cli -h redisdb.consolidated-demo-prod -p 6379 -a "password" ping

# Using Python
python3 -c "
import redis
client = redis.Redis(host='redisdb.consolidated-demo-prod', port=6379, password='password')
print(client.ping())
print(client.info()['redis_version'])
"
```

## 📞 Support

### Log Files
- HolmesGPT logs: Check application logs for detailed error messages
- Redis logs: Check Redis server logs for connection and authentication issues
- InfraInsights logs: Check backend logs for API request issues

### Useful Commands
```bash
# Check HolmesGPT version and loaded toolsets
holmes --version
holmes --list-toolsets

# Test configuration
holmes --config-check

# Validate Redis connection
holmes "Test Redis connection to consolidated-demo-prod"
```

### Environment Information
When reporting issues, include:
- HolmesGPT version
- Python version
- Redis library version (`pip show redis`)
- InfraInsights backend version
- Configuration file or environment variables (sanitized)
- Error logs and stack traces

## 🔗 Related Documentation

- [InfraInsights API Documentation](../INFRAINSIGHTS_API.md)
- [HolmesGPT Configuration Guide](../CONFIG_GUIDE.md)
- [Redis Best Practices](../REDIS_BEST_PRACTICES.md)
- [Troubleshooting Guide](../TROUBLESHOOTING.md)

---

**🎉 Congratulations!** Your InfraInsights Redis Toolset is now ready to provide comprehensive Redis monitoring and analysis capabilities to HolmesGPT! 