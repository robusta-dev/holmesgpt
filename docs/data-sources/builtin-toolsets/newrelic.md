# New Relic

By enabling this toolset, HolmesGPT will be able to fetch logs and traces from New Relic. This allows Holmes to access your application performance data and logs stored in New Relic for investigation purposes.

## Prerequisites

1. A New Relic User API Key
2. Your New Relic Account ID

You can find these in your New Relic account under Administration > API keys and Account settings.

## Configuration

=== "Holmes CLI"

    First, set the following environment variables:

    ```bash
    export NEW_RELIC_USER_KEY="<your New Relic User API key>"
    export NEW_RELIC_ACCOUNT_ID="<your New Relic account ID>"
    ```

    Then add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      newrelic/apm:
        enabled: true
        config:
          region: "US"  # or "EU" for EU region

      kubernetes/logs:
        enabled: false  # Disable default Kubernetes logging if using New Relic for logs
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      additionalEnvVars:
        - name: NEW_RELIC_USER_KEY
          value: "<your New Relic User API key>"
        - name: NEW_RELIC_ACCOUNT_ID
          value: "<your New Relic account ID>"
      toolsets:
        newrelic/apm:
          enabled: true
          config:
            region: "US"  # or "EU" for EU region

        kubernetes/logs:
          enabled: false  # Disable default Kubernetes logging if using New Relic for logs
    ```

## Advanced Configuration

You can customize the New Relic region and other parameters:

```yaml
toolsets:
  newrelic/apm:
    enabled: true
    config:
      region: "US"  # Options: "US" or "EU"
      timeout: 30  # Request timeout in seconds
      max_results: 1000  # Maximum number of results to fetch
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| newrelic_fetch_logs | Fetch logs from New Relic for specified time ranges and filters |
| newrelic_fetch_traces | Fetch distributed traces from New Relic APM |
| newrelic_query_nrql | Execute NRQL queries against New Relic data |
| newrelic_get_app_performance | Get application performance metrics |
