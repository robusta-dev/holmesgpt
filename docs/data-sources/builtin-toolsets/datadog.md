# Datadog

Connect HolmesGPT to Datadog for log analysis and metrics access from your Datadog dashboards.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Prerequisites

1. A Datadog API key with log access permissions
2. A Datadog Application key

You can find these in your Datadog account under Organization Settings > API Keys and Application Keys.

## Configuration

=== "Holmes CLI"

    First, set the following environment variables:

    ```bash
    export DD_API_KEY="your-Datadog-api-key"
    export DD_APP_KEY="your-Datadog-app-key"
    ```

    Then add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:

    ```yaml
    toolsets:
      datadog/logs:
        enabled: true
        config:
          site: "datadoghq.com"  # or datadoghq.eu for EU, etc.

      kubernetes/logs:
        enabled: false  # Disable default Kubernetes logging
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      additionalEnvVars:
        - name: DD_API_KEY
          value: "<your Datadog API key>"
        - name: DD_APP_KEY
          value: "<your Datadog application key>"
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
| datadog_fetch_logs | Fetch logs from Datadog for specified time ranges and filters |
| datadog_search_logs | Search logs in Datadog using query patterns |
