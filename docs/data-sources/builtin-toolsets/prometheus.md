# Prometheus

Connect HolmesGPT to Prometheus for metrics analysis and query generation. This integration enables detection of memory leaks, CPU throttling, queue backlogs, and performance issues.

## Prerequisites

- A running and accessible Prometheus server (or compatible service)
- Network access from HolmesGPT to the Prometheus endpoint

### Supported Prometheus Providers

HolmesGPT works with standard Prometheus and these managed services:

- **[Coralogix](coralogix.md#metrics-configuration-prometheus)** - Full-stack observability platform
- **[Grafana Cloud (Mimir)](../prometheus-providers/grafana-cloud.md)** - Hosted Prometheus/Mimir service
- **[Amazon Managed Prometheus (AMP)](../prometheus-providers/amazon-managed-prometheus.md)** - AWS managed Prometheus service
- **VictoriaMetrics** - Prometheus-compatible monitoring solution

## Configuration

```yaml-toolset-config
# __CLI_EXTRA__: export PROMETHEUS_URL="http://your-prometheus:9090" && holmes ask "show me CPU usage"
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: http://<your-prometheus-service>:9090

      # Optional authentication:
      #headers:
      #    Authorization: "Basic <base_64_encoded_string>"

      # Optional SSL/TLS settings:
      #prometheus_ssl_enabled: true  # Set to false to disable SSL verification (default: true)

      # Optional label filtering:
      #additional_labels:  # Add extra label selectors to all Prometheus queries
      #    cluster: "production"
      #    region: "us-west-2"
```

### Validation

=== "CLI"

    Test your connection:
    ```bash
    holmes ask "Show me the CPU usage for the last hour"
    ```

=== "HolmesGPT Helm Chart"

    After deploying, test the API endpoint directly. See [HTTP API Reference](../../reference/http-api.md) for details.

=== "Robusta Helm Chart"

    Open **Ask Holmes** in the Robusta SaaS platform and ask:
    ```
    Show me the CPU usage for the last hour
    ```

## Troubleshooting



### Finding your Prometheus URL

There are several ways to find your Prometheus URL:

**Option 1: Simple method (port-forwarding)**

```bash
# Find Prometheus services
kubectl get svc -A | grep prometheus

# Port forward for testing
kubectl port-forward svc/<your-prometheus-service> 9090:9090 -n <namespace>
# Then access Prometheus at: http://localhost:9090
```

**Option 2: Advanced method (get full cluster DNS URL)**

If you want to find the full internal DNS URL for Prometheus, run:

```bash
kubectl get svc --all-namespaces -o jsonpath='{range .items[*]}{.metadata.name}{"."}{.metadata.namespace}{".svc.cluster.local:"}{.spec.ports[0].port}{"\n"}{end}' | grep prometheus | grep -Ev 'operat|alertmanager|node|coredns|kubelet|kube-scheduler|etcd|controller' | awk '{print "http://"$1}'
```

This will print all possible Prometheus service URLs in your cluster. Pick the one that matches your deployment.

### Common Issues

- **Connection refused**: Check if the Prometheus URL is accessible from HolmesGPT.
- **Authentication errors**: Verify the headers configuration for secured Prometheus endpoints.
- **SSL certificate errors**:
  - For self-signed certificates, set `prometheus_ssl_enabled: false` to disable verification
  - Or provide a custom CA certificate via the `CERTIFICATE` environment variable (see [Custom SSL Certificates](../../ai-providers/openai-compatible.md#custom-ssl-certificates))


## Advanced Configuration

You can further customize the Prometheus toolset with the following options:

```yaml-toolset-config
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: http://<prometheus-host>:9090
      healthcheck: "-/healthy"  # Path for health checking (default: -/healthy)
      headers:
        Authorization: "Basic <base_64_encoded_string>"
      metrics_labels_time_window_hrs: 48  # Time window (hours) for fetching labels (default: 48)
      metrics_labels_cache_duration_hrs: 12  # How long to cache labels (hours, default: 12)
      fetch_labels_with_labels_api: false  # Use labels API instead of series API (default: false)
      fetch_metadata_with_series_api: false  # Use series API for metadata (default: false)
      tool_calls_return_data: true  # If false, disables returning Prometheus data (default: true)
      prometheus_ssl_enabled: true  # Set to false to disable SSL verification (default: true)
      additional_labels:  # Add extra label selectors to all Prometheus queries (optional)
        cluster: "production"
        region: "us-west-2"
```

**Config option explanations:**

- `prometheus_url`: The base URL for Prometheus. Should include protocol and port.
- `healthcheck`: Path used for health checking Prometheus or Mimir/Cortex endpoint. Defaults to `-/healthy` for Prometheus, use `/ready` for Grafana Mimir.
- `headers`: Extra headers for all Prometheus HTTP requests (e.g., for authentication).
- `metrics_labels_time_window_hrs`: Time window (in hours) for fetching labels. Set to `null` to fetch all labels.
- `metrics_labels_cache_duration_hrs`: How long to cache labels (in hours). Set to `null` to disable caching.
- `fetch_labels_with_labels_api`: Use the Prometheus labels API to fetch labels (can improve performance, but increases HTTP calls).
- `fetch_metadata_with_series_api`: Use the series API for metadata (only set to true if the metadata API is disabled or not working).
- `tool_calls_return_data`: If `false`, disables returning Prometheus data to HolmesGPT (useful if you hit token limits).
- `prometheus_ssl_enabled`: Enable/disable SSL certificate verification. Set to `false` for self-signed certificates (default: `true`).
- `additional_labels`: Dictionary of labels to add to all Prometheus queries. Useful for filtering metrics in multi-cluster or multi-tenant environments.

## SSL/TLS Configuration

### Self-Signed Certificates

If your Prometheus instance uses self-signed certificates, you have two options:

**Option 1: Disable SSL verification** (less secure, but simpler)
```yaml
prometheus/metrics:
  config:
    prometheus_ssl_enabled: false
```

**Option 2: Provide custom CA certificate** (more secure)
```yaml
# Set the CERTIFICATE environment variable with your base64-encoded CA certificate
additionalEnvVars:
  - name: CERTIFICATE
    value: "LS0tLS1CRUdJTi..."  # Your base64-encoded CA certificate
```

The `CERTIFICATE` environment variable applies globally to all HTTPS connections made by Holmes, including Prometheus, AI providers, and other integrations. See [Custom SSL Certificates](../../ai-providers/openai-compatible.md#custom-ssl-certificates) for more details.

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| list_available_metrics | List all available Prometheus metrics |
| execute_prometheus_instant_query | Execute an instant PromQL query |
| execute_prometheus_range_query | Execute a range PromQL query for time series data |
| get_current_time | Get current timestamp for time-based queries |
