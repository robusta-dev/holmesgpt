# OpenSearch logs

By enabling this toolset, HolmesGPT will fetch pod logs from [OpenSearch](https://opensearch.org/).

You **should** enable this toolset to replace the default Kubernetes logs toolset if all your kubernetes pod logs are consolidated inside OpenSearch/Elastic. It will make it easier for HolmesGPT to fetch incident logs, including the ability to precisely consult past logs.

!!! warning "Logging Toolsets"
    Only one logging toolset should be enabled at a time. If you enable this toolset, disable the default `kubernetes/logs` toolset.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      opensearch/logs:
        enabled: true
        config:
          opensearch_url: https://your-opensearch-cluster.com:443
          index_pattern: fluentd-*
          opensearch_auth_header: "ApiKey your-api-key-here"
          labels:
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
            opensearch_url: https://your-opensearch-cluster.com:443 # The URL to your opensearch cluster.
            index_pattern: fluentd-* # The pattern matching the indexes containing the logs. Supports wildcards
            opensearch_auth_header: "ApiKey your-api-key-here" # An optional header value set to the `Authorization` header for every request to opensearch.
            labels: # set the labels according to how values are mapped in your opensearch cluster
              pod: "kubernetes.pod_name"
              namespace: "kubernetes.namespace_name"
              timestamp: "@timestamp"
              message: "message"

        kubernetes/logs:
          enabled: false # HolmesGPT's default logging mechanism MUST be disabled
    ```

    --8<-- "snippets/helm_upgrade_command.md"

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| opensearch_fetch_logs | Fetch logs from OpenSearch for specified pods and time ranges |
| opensearch_search_logs | Search logs in OpenSearch using query patterns |
