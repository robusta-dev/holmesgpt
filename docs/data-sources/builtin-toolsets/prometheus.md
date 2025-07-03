# Prometheus

Connect HolmesGPT to Prometheus for metrics analysis and query generation. Enables detection of memory leaks, CPU throttling, queue backlogs, and performance issues.

## Prerequisites

- Prometheus server running and accessible
- Network connectivity from HolmesGPT to Prometheus endpoint

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
        prometheus/metrics:
            enabled: true
            config:
                prometheus_url: http://prometheus-server:9090

                # optional
                #headers:
                #    Authorization: "Basic <base_64_encoded_string>"
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
        toolsets:
            prometheus/metrics:
                enabled: true
                config:
                    prometheus_url: http://prometheus-server:9090

                    # optional
                    #headers:
                    #    Authorization: "Basic <base_64_encoded_string>"
    ```

    --8<-- "snippets/helm_upgrade_command.md"

💡 **Alternative**: Set `PROMETHEUS_URL` environment variable instead of the config file.

## Validation

Test your connection:

```bash
holmes ask "show me CPU usage for the last hour"
```

## Troubleshooting

### Finding Your Prometheus URL

```bash
# Find Prometheus services
kubectl get svc -A | grep prometheus

# Port forward for testing
kubectl port-forward svc/prometheus-server 9090:80
# Then use: http://localhost:9090
```

### Common Issues

- **Connection refused**: Check if Prometheus URL is accessible from HolmesGPT
- **Authentication errors**: Verify headers configuration for secured Prometheus
- **No metrics returned**: Ensure Prometheus is scraping your targets

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| list_available_metrics | List all available Prometheus metrics |
| execute_prometheus_instant_query | Execute an instant PromQL query |
| execute_prometheus_range_query | Execute a range PromQL query for time series data |
| get_current_time | Get current timestamp for time-based queries |
