# Grafana Cloud (Mimir)

Configure HolmesGPT to use Grafana Cloud's Prometheus/Mimir endpoint for metrics analysis.

## Prerequisites

- Grafana Cloud account
- Service account with MetricsReader role
- Your Grafana Cloud stack information

## Configuration Steps

### 1. Create a Service Account Token

1. Navigate to **Administration → Service accounts** in Grafana Cloud
2. Create a new service account with a descriptive name (e.g., `holmes-metrics-reader`)
3. Assign the **MetricsReader** role
4. Generate a new service account token
5. Copy the generated token (you won't be able to see it again)

### 2. Find Your Prometheus Endpoint

Your Prometheus endpoint URL format:
```
https://<your-stack-name>.grafana.net/api/prom
```

You can find your stack name in your Grafana Cloud portal URL.

### 3. Configure HolmesGPT

=== "CLI"

    Create or edit `~/.holmes/config.yaml`:

    ```yaml
    toolsets:
      prometheus/metrics:
        enabled: true
        config:
          prometheus_url: "https://your-stack.grafana.net/api/prom"
          healthcheck: "/api/v1/query?query=up"  # Required for Mimir
          headers:
            Authorization: "Bearer YOUR_SERVICE_ACCOUNT_TOKEN"

          # Mimir-specific settings
          metrics_labels_time_window_hrs: 168  # 7 days
          fetch_labels_with_labels_api: true
    ```

=== "Kubernetes (Helm)"

    Store your token as a Kubernetes secret:

    ```bash
    kubectl create secret generic grafana-cloud-token \
      --from-literal=GRAFANA_CLOUD_TOKEN='your-service-account-token'
    ```

    Then configure your Helm values:

    ```yaml
    additionalEnvVars:
      - name: GRAFANA_CLOUD_TOKEN
        valueFrom:
          secretKeyRef:
            name: grafana-cloud-token
            key: GRAFANA_CLOUD_TOKEN

    toolsets:
      prometheus/metrics:
        enabled: true
        config:
          prometheus_url: "https://your-stack.grafana.net/api/prom"
          healthcheck: "/api/v1/query?query=up"  # Required for Mimir
          headers:
            Authorization: "Bearer {{ env.GRAFANA_CLOUD_TOKEN }}"

          # Mimir-specific settings
          metrics_labels_time_window_hrs: 168  # 7 days
          fetch_labels_with_labels_api: true
    ```

## Important Configuration Notes

- **healthcheck**: Must be set to `/api/v1/query?query=up` (Mimir doesn't support `-/healthy`)
- **Authorization header**: Must use `Bearer` token format
- **metrics_labels_time_window_hrs**: Can be increased up to your data retention period
- **Rate limits**: Grafana Cloud has rate limits - HolmesGPT respects these automatically

## Validation

Test your configuration:

```bash
holmes ask "Show me the current memory usage metrics"
```

## Troubleshooting

### Authentication Errors
- Verify your service account token is correct
- Ensure the token has MetricsReader permissions
- Check that Authorization header uses `Bearer` prefix

### Rate Limiting
If you encounter rate limit errors:
- Reduce `metrics_labels_cache_duration_hrs` to cache results longer
- Decrease `metrics_labels_time_window_hrs` to query less data

### Connection Issues
- Verify your stack name in the URL is correct
- Ensure the `/api/prom` path is included in the URL
- Check network connectivity to Grafana Cloud

## Additional Options

For all available Prometheus configuration options, see the [main Prometheus documentation](../prometheus.md#advanced-configuration).
