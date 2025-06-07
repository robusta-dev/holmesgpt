# Prometheus

By enabling this toolset, HolmesGPT will be able to generate graphs from prometheus metrics as well as help you write and validate prometheus queries. HolmesGPT can also detect memory leak patterns, CPU throttling, lagging queues, and high latency issues.

Prior to generating a PromQL query, HolmesGPT tends to list the available metrics. This is done to ensure the metrics used in PromQL are actually available.

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
        prometheus/metrics:
            enabled: true
            config:
                # see below how to find prometheus_url
                prometheus_url: http://<prometheus host>:9090 # e.g. http://robusta-kube-prometheus-st-prometheus.default.svc.cluster.local:9090

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
                    # see below how to find prometheus_url
                    prometheus_url: http://<prometheus host>:9090 # e.g. http://robusta-kube-prometheus-st-prometheus.default.svc.cluster.local:9090

                    # optional
                    #headers:
                    #    Authorization: "Basic <base_64_encoded_string>"
    ```

It is also possible to set the `PROMETHEUS_URL` environment variable instead of the above `prometheus_url` config key.

## Advanced configuration

Below is the full list of options for this toolset:

```yaml
prometheus/metrics:
  enabled: true
  config:
    prometheus_url: http://localhost:9090
    headers:
      Authorization: "Basic <base_64_encoded_string>"
    # Optional: timeout for requests in seconds
    timeout: 30
    # Optional: maximum number of metrics to fetch
    max_metrics: 1000
    # Optional: cache duration for metrics list
    cache_duration: 300
```

## Finding your Prometheus URL

To find your Prometheus URL, you can:

1. **For Kubernetes clusters with Prometheus Operator:**
   ```bash
   kubectl get prometheus -A
   kubectl get svc -A | grep prometheus
   ```

2. **Port forward to access Prometheus locally:**
   ```bash
   kubectl port-forward svc/prometheus-server 9090:80
   # Then use: http://localhost:9090
   ```

3. **Check your Helm releases:**
   ```bash
   helm list -A | grep prometheus
   ```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| list_available_metrics | List all available Prometheus metrics |
| execute_prometheus_instant_query | Execute an instant PromQL query |
| execute_prometheus_range_query | Execute a range PromQL query for time series data |
| get_current_time | Get current timestamp for time-based queries |
