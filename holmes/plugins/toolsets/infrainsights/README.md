# InfraInsights Toolsets for HolmesGPT

This package provides custom toolsets for HolmesGPT that integrate with the InfraInsights multi-instance architecture. These toolsets enable automated investigation and RCA (Root Cause Analysis) for various data stores and services managed by InfraInsights.

## Overview

The InfraInsights toolsets provide HolmesGPT with the ability to:

- **Multi-Instance Support**: Automatically work with multiple instances of the same service type (production, staging, development, etc.)
- **Intelligent Instance Selection**: Identify the correct service instance from user prompts using keyword matching and context
- **Secure Credential Management**: Fetch credentials securely from InfraInsights without hardcoding them
- **User Context Awareness**: Use current user context to determine which instance to investigate
- **Comprehensive Investigation Tools**: Provide tools for deep investigation of each service type

## Supported Services

### 1. Elasticsearch Toolset
**Service Type**: `elasticsearch`

**Tools**:
- `list_elasticsearch_indices`: List all indices with health and document counts
- `get_elasticsearch_cluster_health`: Get detailed cluster health information
- `search_elasticsearch_documents`: Search for documents with custom queries
- `get_elasticsearch_index_mapping`: Get field mappings for indices

**Use Cases**:
- Investigate log analysis issues
- Check cluster health and performance
- Search for specific error patterns
- Analyze index mappings and data structure

### 2. Kafka Toolset
**Service Type**: `kafka`

**Tools**:
- `list_kafka_topics`: List all topics with partition and replication info
- `list_kafka_consumer_groups`: List all consumer groups with their state
- `describe_kafka_topic`: Get detailed topic information and configuration
- `get_kafka_consumer_group_lag`: Get lag information for consumer groups

**Use Cases**:
- Investigate message processing issues
- Check consumer group lag and performance
- Analyze topic configuration and partitioning
- Monitor cluster health and broker status

### 3. Kubernetes Toolset
**Service Type**: `kubernetes`

**Tools**:
- `list_kubernetes_nodes`: List all nodes with status and resource info
- `get_kubernetes_node_details`: Get detailed node information including pods
- `list_kubernetes_pods`: List pods with filtering by namespace/node
- `get_kubernetes_cluster_health`: Get overall cluster health status

**Use Cases**:
- Investigate pod scheduling issues
- Check node health and resource usage
- Analyze cluster performance and capacity
- Debug application deployment problems

### 4. MongoDB Toolset
**Service Type**: `mongodb`

**Tools**:
- `list_mongodb_databases`: List all databases with sizes and collection counts
- `list_mongodb_collections`: List collections in a database with document counts
- `search_mongodb_documents`: Search for documents with custom queries
- `get_mongodb_server_status`: Get server performance metrics and status

**Use Cases**:
- Investigate database performance issues
- Check collection sizes and document counts
- Search for specific data patterns
- Monitor server health and metrics

### 5. Redis Toolset
**Service Type**: `redis`

**Tools**:
- `get_redis_info`: Get server information and performance metrics
- `list_redis_keys`: List keys with pattern matching and metadata
- `get_redis_key_value`: Get value and metadata of specific keys
- `get_redis_memory_usage`: Get detailed memory usage information

**Use Cases**:
- Investigate cache performance issues
- Check memory usage and fragmentation
- Analyze key patterns and usage
- Monitor server health and connections

## Installation and Configuration

### 1. Prerequisites

- HolmesGPT installed and configured
- InfraInsights API accessible
- Python dependencies: `requests`, `elasticsearch`, `confluent-kafka`, `pymongo`, `redis`

### 2. Configuration

Create a configuration file (e.g., `infrainsights_config.yaml`) based on the example:

```yaml
toolsets:
  infrainsights_elasticsearch:
    type: "custom"
    enabled: true
    description: "InfraInsights Elasticsearch Investigation Tools"
    config:
      infrainsights_url: "http://your-infrainsights-api:3000"
      api_key: "your-api-key"
      timeout: 30
```

### 3. Environment Variables

Alternatively, use environment variables:

```bash
export INFRAINSIGHTS_URL="http://your-infrainsights-api:3000"
export INFRAINSIGHTS_API_KEY="your-api-key"
export INFRAINSIGHTS_USERNAME="your-username"
export INFRAINSIGHTS_PASSWORD="your-password"
export INFRAINSIGHTS_TIMEOUT=30
```

## Usage Examples

### Basic Usage

1. **Instance Identification**: The toolsets automatically identify which service instance to use based on your prompt:

```
"Check the health of my production Elasticsearch cluster"
"Show me all topics in the staging Kafka instance"
"List nodes in the development Kubernetes cluster"
```

2. **Context-Aware Selection**: If you have a current context set, the toolsets will use that:

```
"Get the current cluster health"  # Uses your current Kubernetes context
"List all indices"  # Uses your current Elasticsearch context
```

3. **Explicit Instance Selection**: You can also specify the instance explicitly:

```
"Check the health of the 'prod-es-01' Elasticsearch instance"
"List topics in the 'staging-kafka' Kafka cluster"
```

### Advanced Investigation Workflows

#### 1. Elasticsearch Log Analysis
```
"Investigate the recent error logs in my production Elasticsearch cluster"
```
This will:
- Identify the production Elasticsearch instance
- Check cluster health
- List relevant indices
- Search for error patterns
- Provide analysis and recommendations

#### 2. Kafka Message Processing Issues
```
"Check why messages are not being processed in the user-events topic"
```
This will:
- Identify the Kafka instance
- List consumer groups
- Check consumer lag
- Analyze topic configuration
- Identify potential bottlenecks

#### 3. Kubernetes Pod Issues
```
"Investigate why pods are not starting on node ip-10-228-39-74"
```
This will:
- Get detailed node information
- List pods on the specific node
- Check node health and resources
- Analyze pod scheduling issues
- Provide troubleshooting steps

#### 4. MongoDB Performance Issues
```
"Check why the users database is slow in production"
```
This will:
- Get server status and metrics
- List database and collection stats
- Analyze query patterns
- Check resource usage
- Provide optimization recommendations

#### 5. Redis Memory Issues
```
"Investigate memory usage in the session cache Redis instance"
```
This will:
- Get server information and memory stats
- List key patterns and sizes
- Check memory fragmentation
- Analyze memory usage patterns
- Provide cleanup recommendations

## Architecture

### Core Components

1. **InfraInsightsClient**: Handles communication with the InfraInsights API
2. **BaseInfraInsightsToolset**: Base class providing common functionality
3. **Service-Specific Toolsets**: Specialized toolsets for each service type
4. **Instance Discovery**: Automatic identification of service instances
5. **Credential Management**: Secure handling of connection credentials

### Instance Selection Logic

The toolsets use a sophisticated instance selection algorithm:

1. **Explicit Specification**: If instance_id or instance_name is provided
2. **Prompt Analysis**: Keyword matching against instance names, environments, and tags
3. **User Context**: Current user's selected instance for the service type
4. **Fallback**: First available active instance

### Security Features

- **Credential Caching**: Secure caching of credentials with TTL
- **Access Control**: Respects InfraInsights user permissions
- **Audit Logging**: Logs all operations for security compliance
- **Error Handling**: Secure error messages without exposing sensitive data

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Check InfraInsights API URL and authentication
   - Verify network connectivity
   - Check API key or credentials

2. **Instance Not Found**:
   - Verify the instance exists in InfraInsights
   - Check user permissions for the instance
   - Ensure the service type matches

3. **Authentication Errors**:
   - Verify API key or username/password
   - Check if credentials have expired
   - Ensure proper permissions

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('holmes.plugins.toolsets.infrainsights').setLevel(logging.DEBUG)
```

## Contributing

To add support for new services:

1. Create a new toolset class inheriting from `BaseInfraInsightsToolset`
2. Implement service-specific tools inheriting from `BaseInfraInsightsTool`
3. Add connection management for the service
4. Update the main toolsets `__init__.py` file
5. Add configuration examples and documentation

## License

This project is licensed under the same license as HolmesGPT.

## Support

For issues and questions:
- Check the troubleshooting section
- Review the example configurations
- Consult the HolmesGPT documentation
- Open an issue in the repository 