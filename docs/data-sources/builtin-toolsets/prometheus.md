# Prometheus

Connect HolmesGPT to Prometheus for metrics analysis and query generation. This integration enables detection of memory leaks, CPU throttling, queue backlogs, and performance issues.

## Prerequisites

- A running and accessible Prometheus server
- Ensure HolmesGPT can connect to the Prometheus endpoint

## Configuration


=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
        prometheus/metrics:
            enabled: true
            config:
                prometheus_url: http://prometheus-server:9090 # localhost:9090 if port-forwarded

                # Optional:
                #headers:
                #    Authorization: "Basic <base_64_encoded_string>"
    ```

    --8<-- "snippets/toolset_refresh_warning.md"


=== "Robusta Helm Chart"

    ```yaml
    holmes:
        toolsets:
            prometheus/metrics:
                enabled: true
                config:
                    prometheus_url: http://<your-prometheus-service>:9090

                    # Optional:
                    #headers:
                    #    Authorization: "Basic <base_64_encoded_string>"
    ```

    --8<-- "snippets/helm_upgrade_command.md"


💡 **Alternative**: Set the `PROMETHEUS_URL` environment variable instead of using the config file.

## Validation

To test your connection, run:

```bash
holmes ask "Show me the CPU usage for the last hour"
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
- **No metrics returned**: Ensure that Prometheus is scraping your targets.


## Advanced Configuration

You can further customize the Prometheus toolset with the following options:

```yaml
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

---

## Coralogix Prometheus Configuration

To use a Coralogix PromQL endpoint with HolmesGPT:

1. Go to [Coralogix Documentation](https://coralogix.com/docs/integrations/coralogix-endpoints/#promql) and choose the relevant PromQL endpoint for your region.
2. In Coralogix, create an API key with permissions to query metrics (Data Flow → API Keys).
3. Create a Kubernetes secret for the API key and expose it as an environment variable in your Helm values:

    ```yaml
    holmes:
      additionalEnvVars:
        - name: CORALOGIX_API_KEY
          valueFrom:
            secretKeyRef:
              name: coralogix-api-key
              key: CORALOGIX_API_KEY
    ```

4. Add the following under your toolsets in the Helm chart:

    ```yaml
    holmes:
      toolsets:
        prometheus/metrics:
          enabled: true
          config:
            healthcheck: "/api/v1/query?query=up"  # This is important for Coralogix
            prometheus_url: "https://prom-api.eu2.coralogix.com"  # Use your region's endpoint
            headers:
              token: "{{ env.CORALOGIX_API_KEY }}"
            metrics_labels_time_window_hrs: 72
            metrics_labels_cache_duration_hrs: 12
            fetch_labels_with_labels_api: true
            tool_calls_return_data: true
            fetch_metadata_with_series_api: true
    ```

---

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| list_available_metrics | List all available Prometheus metrics |
| execute_prometheus_instant_query | Execute an instant PromQL query |
| execute_prometheus_range_query | Execute a range PromQL query for time series data |
| get_current_time | Get current timestamp for time-based queries |
