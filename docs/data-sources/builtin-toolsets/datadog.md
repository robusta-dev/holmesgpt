# DataDog

Connect HolmesGPT to DataDog for log analysis and metrics access from your DataDog dashboards.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Prerequisites

1. A DataDog API key with log access permissions
2. A DataDog Application key

You can find these in your DataDog account under Organization Settings > API Keys and Application Keys.

## Configuration

=== "Holmes CLI"

    First, set the following environment variables:

    ```bash
    export DD_API_KEY="your-datadog-api-key"
    export DD_APP_KEY="your-datadog-app-key"
    ```

    Then add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      datadog/logs:
        enabled: true
        config:
          site: "datadoghq.com"  # or datadoghq.eu for EU, etc.

      kubernetes/logs:
        enabled: false  # Disable default Kubernetes logging
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      additionalEnvVars:
        - name: DD_API_KEY
          value: "<your DataDog API key>"
        - name: DD_APP_KEY
          value: "<your DataDog application key>"
      toolsets:
        datadog/logs:
          enabled: true
          config:
            site: "datadoghq.com"  # or datadoghq.eu for EU, etc.

        kubernetes/logs:
          enabled: false  # Disable default Kubernetes logging
    ```

    --8<-- "snippets/helm_upgrade_command.md"

## Validation

Test your configuration:

```bash
holmes ask "show me recent application errors"
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| datadog_fetch_logs | Fetch logs from DataDog for specified time ranges and filters |
| datadog_search_logs | Search logs in DataDog using query patterns |
