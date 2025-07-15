# OpenSearch Logs

Connect HolmesGPT to OpenSearch for centralized log analysis and historical log access.

## Prerequisites

- OpenSearch cluster with Kubernetes pod logs
- API key with read access to log indices
- Network connectivity from HolmesGPT to OpenSearch

--8<-- "snippets/toolsets_that_provide_logging.md"

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
      opensearch/logs:
        enabled: true
        config:
          opensearch_url: https://opensearch.example.com:443
          index_pattern: kubernetes-*  # Pattern matching log indices
          opensearch_auth_header: "ApiKey YOUR_API_KEY"
          labels:  # Map fields to match your log structure
            pod: "kubernetes.pod_name"
            namespace: "kubernetes.namespace_name"
            timestamp: "@timestamp"
            message: "message"

      kubernetes/logs:
        enabled: false # Disable default Kubernetes logging
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        opensearch/logs:
          enabled: true
          config:
            opensearch_url: https://opensearch.example.com:443
            index_pattern: kubernetes-*
            opensearch_auth_header: "ApiKey YOUR_API_KEY"
            labels:
              pod: "kubernetes.pod_name"
              namespace: "kubernetes.namespace_name"
              timestamp: "@timestamp"
              message: "message"

        kubernetes/logs:
          enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

    --8<-- "snippets/helm_upgrade_command.md"

## Validation

Test your configuration:

```bash
holmes ask "show me recent errors from the payment service"
```

## Troubleshooting

### Common Issues

- **Authentication errors**: Verify your API key has read access to the specified indices
- **No logs found**: Check that `index_pattern` matches your actual OpenSearch indices
- **Field mapping errors**: Ensure `labels` section maps to correct field names in your logs

### Finding Your Index Pattern

```bash
# List indices to find the correct pattern
curl -X GET "https://opensearch.example.com/_cat/indices?v" \
  -H "Authorization: ApiKey YOUR_API_KEY"
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| opensearch_fetch_logs | Fetch logs from OpenSearch for specified pods and time ranges |
| opensearch_search_logs | Search logs in OpenSearch using query patterns |
