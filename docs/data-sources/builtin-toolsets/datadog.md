# DataDog

By enabling this toolset, HolmesGPT will be able to fetch logs from DataDog. This allows Holmes to access your application logs stored in DataDog for investigation purposes.

!!! warning "Logging Toolsets"
    Only one logging toolset should be enabled at a time. If you enable this toolset, disable the default `kubernetes/logs` toolset.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Prerequisites

1. A DataDog API key with log access permissions
2. A DataDog Application key

You can find these in your DataDog account under Organization Settings > API Keys and Application Keys.

## Configuration

=== "Holmes CLI"

    First, set the following environment variables:

    ```bash
    export DD_API_KEY="<your DataDog API key>"
    export DD_APP_KEY="<your DataDog application key>"
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

## Advanced Configuration

You can customize the DataDog site and other parameters:

```yaml
toolsets:
  datadog/logs:
    enabled: true
    config:
      site: "datadoghq.com"  # Options: datadoghq.com, datadoghq.eu, us3.datadoghq.com, etc.
      timeout: 30  # Request timeout in seconds
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| datadog_fetch_logs | Fetch logs from DataDog for specified time ranges and filters |
| datadog_search_logs | Search logs in DataDog using query patterns |
