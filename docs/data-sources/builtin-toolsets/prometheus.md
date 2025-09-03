# Prometheus

Connect HolmesGPT to Prometheus for metrics analysis and query generation. This integration enables detection of memory leaks, CPU throttling, queue backlogs, and performance issues.

## Prerequisites

- A running and accessible Prometheus server
- Ensure HolmesGPT can connect to the Prometheus endpoint

## Configuration

=== "CLI"

    Create or edit your `~/.holmes/config.yaml`:

    ```yaml
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

    💡 **Alternative**: Set the `PROMETHEUS_URL` environment variable instead of using the config file:
    ```bash
    export PROMETHEUS_URL="http://your-prometheus:9090"
    holmes ask "show me CPU usage"
    ```

=== "HolmesGPT Helm Chart"

    Configure Prometheus in your `values.yaml`:

    ```yaml
    holmes:
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

=== "Robusta Helm Chart"

    When using Robusta's integrated HolmesGPT, configure Prometheus in your `values.yaml`:

    ```yaml
    globalConfig:
      custom_toolsets:
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
- **SSL certificate errors**:
  - For self-signed certificates, set `prometheus_ssl_enabled: false` to disable verification
  - Or provide a custom CA certificate via the `CERTIFICATE` environment variable (see [Custom SSL Certificates](../../ai-providers/openai-compatible.md#custom-ssl-certificates))


## Advanced Configuration

You can further customize the Prometheus toolset with the following options:

=== "CLI"

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
          prometheus_ssl_enabled: true  # Set to false to disable SSL verification (default: true)
          additional_labels:  # Add extra label selectors to all Prometheus queries (optional)
            cluster: "production"
            region: "us-west-2"
    ```

=== "HolmesGPT Helm Chart"

    ```yaml
    holmes:
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

=== "Robusta Helm Chart"

    ```yaml
    globalConfig:
      custom_toolsets:
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

    # Note: Some Robusta versions require additional RBAC permissions:
    customClusterRoleRules:
      - apiGroups: [""]
        resources: ["services"]
        verbs: ["get", "list", "watch"]
      - apiGroups: ["apps"]
        resources: ["deployments", "replicasets", "daemonsets", "statefulsets"]
        verbs: ["get", "list", "watch"]
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

## Grafana Cloud (Mimir) Configuration

To connect HolmesGPT to Grafana Cloud's Prometheus/Mimir endpoint:

1. **Create a service account token in Grafana Cloud:**
   - Navigate to "Administration → Service accounts"
   - Create a new service account
   - Generate a service account token (starts with `glsa_`)

2. **Find your Prometheus datasource UID:**
   ```bash
   curl -H "Authorization: Bearer YOUR_GLSA_TOKEN" \
        "https://YOUR-INSTANCE.grafana.net/api/datasources" | \
        jq '.[] | select(.type=="prometheus") | {name, uid}'
   ```

3. **Configure HolmesGPT:**
   ```yaml
   holmes:
     toolsets:
       prometheus/metrics:
         enabled: true
         config:
           prometheus_url: https://YOUR-INSTANCE.grafana.net/api/datasources/proxy/uid/PROMETHEUS_DATASOURCE_UID
           fetch_labels_with_labels_api: false  # Important for Mimir
           fetch_metadata_with_series_api: true  # Important for Mimir
           headers:
             Authorization: Bearer YOUR_GLSA_TOKEN
   ```

**Important notes:**

- Use the proxy endpoint URL format `/api/datasources/proxy/uid/` - this handles authentication and routing to Mimir automatically
- Set `fetch_labels_with_labels_api: false` for optimal Mimir compatibility
- Set `fetch_metadata_with_series_api: true` for proper metadata retrieval
