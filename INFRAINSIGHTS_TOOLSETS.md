# InfraInsights Toolsets for HolmesGPT

This document describes how to use the InfraInsights toolsets with HolmesGPT for automated investigation and root cause analysis (RCA) of multi-instance infrastructure services.

## Overview

The InfraInsights toolsets extend HolmesGPT's capabilities to work with the InfraInsights multi-instance architecture. These toolsets provide investigation tools for:

- **Elasticsearch**: Cluster health, indices, document search, and mapping analysis
- **Kafka**: Topics, consumer groups, lag analysis, and configuration
- **Kubernetes**: Nodes, pods, cluster health, and resource monitoring
- **MongoDB**: Databases, collections, document search, and server status
- **Redis**: Keys, memory usage, server information, and performance metrics

## Key Features

### Multi-Instance Support
- Automatically work with multiple instances of the same service type
- Support for production, staging, development, and other environments
- Intelligent instance selection based on user prompts and context

### Intelligent Instance Selection
The toolsets use a sophisticated algorithm to identify the correct service instance:

1. **Explicit Specification**: If `instance_id` or `instance_name` is provided
2. **Prompt Analysis**: Keyword matching against instance names, environments, and tags
3. **User Context**: Current user's selected instance for the service type
4. **Fallback**: First available active instance

### Secure Credential Management
- Fetch credentials securely from InfraInsights API
- No hardcoded credentials in configuration
- Support for JWT-based authentication
- Automatic credential refresh and caching

## Installation

### 1. Prerequisites

- HolmesGPT installed and configured
- InfraInsights API accessible
- Python dependencies installed (see `requirements.txt`)

### 2. Install Dependencies

```bash
cd /path/to/holmesgpt
pip install -r holmes/plugins/toolsets/infrainsights/requirements.txt
```

### 3. Configure Authentication

#### Option A: Generate JWT Token

1. Set up the `TOKEN_GENERATOR_SECRET` in your InfraInsights backend:
   ```bash
   # Add to your .env file
   TOKEN_GENERATOR_SECRET=your-secure-secret-here
   ```

2. Generate a JWT token:
   ```bash
   curl -X POST http://localhost:3001/api/token/generate-token \
     -H "Content-Type: application/json" \
     -d '{
       "secret": "your-token-generator-secret-here",
       "email": "admin@yourcompany.com",
       "roles": ["Admin", "PowerUser"]
     }'
   ```

#### Option B: Use Environment Variables

```bash
export INFRAINSIGHTS_URL="http://localhost:3001"
export INFRAINSIGHTS_API_KEY="your-jwt-token-here"
export INFRAINSIGHTS_TIMEOUT=30
```

### 4. Configure HolmesGPT

Create a configuration file (e.g., `infrainsights_config.yaml`):

```yaml
toolsets:
  infrainsights_elasticsearch:
    type: "custom"
    enabled: true
    description: "InfraInsights Elasticsearch Investigation Tools"
    config:
      infrainsights_url: "http://localhost:3001"
      api_key: "your-jwt-token-here"
      timeout: 30

  infrainsights_kafka:
    type: "custom"
    enabled: true
    description: "InfraInsights Kafka Investigation Tools"
    config:
      infrainsights_url: "http://localhost:3001"
      api_key: "your-jwt-token-here"
      timeout: 30

  infrainsights_kubernetes:
    type: "custom"
    enabled: true
    description: "InfraInsights Kubernetes Investigation Tools"
    config:
      infrainsights_url: "http://localhost:3001"
      api_key: "your-jwt-token-here"
      timeout: 30

  infrainsights_mongodb:
    type: "custom"
    enabled: true
    description: "InfraInsights MongoDB Investigation Tools"
    config:
      infrainsights_url: "http://localhost:3001"
      api_key: "your-jwt-token-here"
      timeout: 30

  infrainsights_redis:
    type: "custom"
    enabled: true
    description: "InfraInsights Redis Investigation Tools"
    config:
      infrainsights_url: "http://localhost:3001"
      api_key: "your-jwt-token-here"
      timeout: 30
```

### 5. Start HolmesGPT

```bash
# Start HolmesGPT with the InfraInsights configuration
python holmes.py --config infrainsights_config.yaml
```

## Usage Examples

### Elasticsearch Investigation

#### Basic Queries
```
"Check the health of my production Elasticsearch cluster"
"List all indices in the staging Elasticsearch instance"
"Search for error logs in the development Elasticsearch cluster"
```

#### Advanced Investigation
```
"Investigate the recent error logs in my production Elasticsearch cluster"
```
This will:
- Identify the production Elasticsearch instance
- Check cluster health
- List relevant indices
- Search for error patterns
- Provide analysis and recommendations

### Kafka Investigation

#### Basic Queries
```
"List all topics in the production Kafka cluster"
"Check consumer group lag in the staging Kafka instance"
"Describe the user-events topic configuration"
```

#### Advanced Investigation
```
"Check why messages are not being processed in the user-events topic"
```
This will:
- Identify the Kafka instance
- List consumer groups
- Check consumer lag
- Analyze topic configuration
- Identify potential bottlenecks

### Kubernetes Investigation

#### Basic Queries
```
"List all nodes in the production Kubernetes cluster"
"Get detailed information about node ip-10-228-39-74"
"List pods in the default namespace"
```

#### Advanced Investigation
```
"Investigate why pods are not starting on node ip-10-228-39-74"
```
This will:
- Get detailed node information
- List pods on the specific node
- Check node health and resources
- Analyze pod scheduling issues
- Provide troubleshooting steps

### MongoDB Investigation

#### Basic Queries
```
"List all databases in the production MongoDB instance"
"Check server status in the staging MongoDB cluster"
"Search for user documents in the users collection"
```

#### Advanced Investigation
```
"Check why the users database is slow in production"
```
This will:
- Get server status and metrics
- List database and collection stats
- Analyze query patterns
- Check resource usage
- Provide optimization recommendations

### Redis Investigation

#### Basic Queries
```
"Get Redis server information for the production instance"
"List all keys in the session cache Redis instance"
"Check memory usage in the staging Redis cluster"
```

#### Advanced Investigation
```
"Investigate memory usage in the session cache Redis instance"
```
This will:
- Get server information and memory stats
- List key patterns and sizes
- Check memory fragmentation
- Analyze memory usage patterns
- Provide cleanup recommendations

## Tool Reference

### Elasticsearch Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_elasticsearch_indices` | List all indices with health and document counts | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `get_elasticsearch_cluster_health` | Get detailed cluster health information | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `search_elasticsearch_documents` | Search for documents with custom queries | `instance_id`, `instance_name`, `user_id`, `prompt`, `index_pattern`, `query`, `size`, `sort` |
| `get_elasticsearch_index_mapping` | Get field mappings for indices | `instance_id`, `instance_name`, `user_id`, `prompt`, `index_name` |

### Kafka Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_kafka_topics` | List all topics with partition and replication info | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `list_kafka_consumer_groups` | List all consumer groups with their state | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `describe_kafka_topic` | Get detailed topic information and configuration | `instance_id`, `instance_name`, `user_id`, `prompt`, `topic_name` |
| `get_kafka_consumer_group_lag` | Get lag information for consumer groups | `instance_id`, `instance_name`, `user_id`, `prompt`, `group_id` |

### Kubernetes Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_kubernetes_nodes` | List all nodes with status and resource info | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `get_kubernetes_node_details` | Get detailed node information including pods | `instance_id`, `instance_name`, `user_id`, `prompt`, `node_name` |
| `list_kubernetes_pods` | List pods with filtering by namespace/node | `instance_id`, `instance_name`, `user_id`, `prompt`, `namespace`, `node_name` |
| `get_kubernetes_cluster_health` | Get overall cluster health status | `instance_id`, `instance_name`, `user_id`, `prompt` |

### MongoDB Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_mongodb_databases` | List all databases with sizes and collection counts | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `list_mongodb_collections` | List collections in a database with document counts | `instance_id`, `instance_name`, `user_id`, `prompt`, `database_name` |
| `search_mongodb_documents` | Search for documents with custom queries | `instance_id`, `instance_name`, `user_id`, `prompt`, `database_name`, `collection_name`, `query`, `limit`, `sort` |
| `get_mongodb_server_status` | Get server performance metrics and status | `instance_id`, `instance_name`, `user_id`, `prompt` |

### Redis Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_redis_info` | Get server information and performance metrics | `instance_id`, `instance_name`, `user_id`, `prompt` |
| `list_redis_keys` | List keys with pattern matching and metadata | `instance_id`, `instance_name`, `user_id`, `prompt`, `pattern`, `limit` |
| `get_redis_key_value` | Get value and metadata of specific keys | `instance_id`, `instance_name`, `user_id`, `prompt`, `key` |
| `get_redis_memory_usage` | Get detailed memory usage information | `instance_id`, `instance_name`, `user_id`, `prompt` |

## Troubleshooting

### Common Issues

#### 1. Connection Errors
**Symptoms**: "Failed to connect to InfraInsights API"
**Solutions**:
- Check InfraInsights API URL and authentication
- Verify network connectivity
- Check API key or credentials
- Ensure InfraInsights backend is running

#### 2. Instance Not Found
**Symptoms**: "Instance not found" or "No matching instances"
**Solutions**:
- Verify the instance exists in InfraInsights
- Check user permissions for the instance
- Ensure the service type matches
- Try using explicit instance_id or instance_name

#### 3. Authentication Errors
**Symptoms**: "Authentication failed" or "Invalid token"
**Solutions**:
- Verify API key or username/password
- Check if credentials have expired
- Ensure proper permissions
- Regenerate JWT token if needed

#### 4. Toolset Not Loading
**Symptoms**: "Toolset failed to initialize"
**Solutions**:
- Check Python dependencies are installed
- Verify configuration format
- Check logs for specific error messages
- Ensure all required environment variables are set

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('holmes.plugins.toolsets.infrainsights').setLevel(logging.DEBUG)
```

### Testing Configuration

Test your configuration with a simple query:

```
"List all nodes in my Kubernetes cluster"
```

If successful, you should see:
1. Instance selection in the logs
2. API calls to InfraInsights
3. Node data returned

## Advanced Configuration

### Environment Variables

You can use environment variables instead of hardcoded values:

```bash
export INFRAINSIGHTS_URL="http://your-infrainsights-api:3000"
export INFRAINSIGHTS_API_KEY="your-jwt-token"
export INFRAINSIGHTS_USERNAME="your-username"
export INFRAINSIGHTS_PASSWORD="your-password"
export INFRAINSIGHTS_TIMEOUT=30
```

### Custom Instance Selection

You can customize instance selection logic by modifying the `get_instance_from_params` method in the base toolset.

### Caching Configuration

The InfraInsights client includes caching for:
- Service instances (5 minutes TTL)
- Credentials (10 minutes TTL)
- API responses (configurable per tool)

## Contributing

To add support for new services:

1. Create a new toolset class inheriting from `BaseInfraInsightsToolset`
2. Implement service-specific tools inheriting from `BaseInfraInsightsTool`
3. Add connection management for the service
4. Update the main toolsets `__init__.py` file
5. Add configuration examples and documentation

## Support

For issues and questions:
- Check the troubleshooting section
- Review the example configurations
- Consult the HolmesGPT documentation
- Open an issue in the repository

## License

This project is licensed under the same license as HolmesGPT. 