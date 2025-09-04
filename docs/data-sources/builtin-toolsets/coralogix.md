# Coralogix

Coralogix is a full-stack observability platform. HolmesGPT integrates with Coralogix to fetch both logs and metrics.

## Overview

**[Logs Integration](#logs-configuration)**: Fetch and analyze pod logs from Coralogix's log management system.

**[Metrics Integration](#metrics-configuration)**: Query metrics using Coralogix's PromQL-compatible endpoint.

--8<-- "snippets/toolsets_that_provide_logging.md"

## Capabilities

| Toolset | Tool Name | Description |
|---------|-----------|-------------|
| coralogix/logs | fetch_pod_logs | Fetch logs from Coralogix for specified pods and time ranges |
| prometheus/metrics | execute_prometheus_instant_query | Execute instant PromQL queries against Coralogix |
| prometheus/metrics | execute_prometheus_range_query | Execute range PromQL queries against Coralogix |

## Prerequisites

1. **API Key**: A [Coralogix API key](https://coralogix.com/docs/developer-portal/apis/data-query/direct-archive-query-http-api/#api-key) with `DataQuerying` permission preset
2. **Domain**: Your [Coralogix domain](https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/) (e.g., `eu2.coralogix.com`)
3. **Team Hostname**: Your team's [name or hostname](https://coralogix.com/docs/user-guides/account-management/organization-management/create-an-organization/#teams-in-coralogix) (e.g., `your-company-name`)

**Finding Your Domain and Team**: You can deduce these from your Coralogix UI URL. For example, if you access Coralogix at `https://my-team.app.eu2.coralogix.com/`, then:
- `team_hostname` = `my-team`
- `domain` = `eu2.coralogix.com`

## Logs Configuration

```yaml-toolset-config
toolsets:
  coralogix/logs:
    enabled: true
    config:
      api_key: "<your Coralogix API key>"
      domain: "eu2.coralogix.com"
      team_hostname: "your-company-name"

  kubernetes/logs:
    enabled: false  # Disable default Kubernetes logging
```

### Advanced Settings

#### Complete Configuration Example

Here's a full example with all available settings:

```yaml-toolset-config
toolsets:
  coralogix/logs:
    enabled: true
    config:
      api_key: "<your Coralogix API key>"
      domain: "eu2.coralogix.com"
      team_hostname: "your-company-name"

      # Custom field mappings (if your logs use non-standard field names)
      labels:
        namespace: "resource.attributes.k8s.namespace.name"  # Default
        pod: "resource.attributes.k8s.pod.name"              # Default
        log_message: "logRecord.body"                        # Default
        timestamp: "logRecord.attributes.time"               # Default

      # Logs retrieval strategy
      logs_retrieval_methodology: "ARCHIVE_FALLBACK"  # Default

  kubernetes/logs:
    enabled: false  # Disable default Kubernetes logging
```

#### Configuration Options

| Option | Description | Default | Values |
|--------|-------------|---------|--------|
| `api_key` | Coralogix API key with DataQuerying permission | *Required* | String |
| `domain` | Your Coralogix domain (e.g., `eu2.coralogix.com`) | *Required* | String |
| `team_hostname` | Your team's name/hostname | *Required* | String |
| `logs_retrieval_methodology` | Strategy for querying log tiers | `ARCHIVE_FALLBACK` | See below |
| `labels.namespace` | Field path for Kubernetes namespace | `resource.attributes.k8s.namespace.name` | String |
| `labels.pod` | Field path for Kubernetes pod name | `resource.attributes.k8s.pod.name` | String |
| `labels.log_message` | Field path for log message content | `logRecord.body` | String |
| `labels.timestamp` | Field path for log timestamp | `logRecord.attributes.time` | String |

#### Logs Retrieval Strategies

Coralogix stores logs in two tiers:

- **Frequent Search**: Fast queries with limited retention
- **Archive**: Slower queries with longer retention

To configure the retrieval strategy, set the `logs_retrieval_methodology` option in your configuration:

| Strategy | Description |
|----------|-------------|
| `ARCHIVE_FALLBACK` | **Recommended** - Try Frequent Search first, fallback to Archive if no results |
| `FREQUENT_SEARCH_ONLY` | Only search Frequent Search tier |
| `ARCHIVE_ONLY` | Only search Archive tier |
| `BOTH_FREQUENT_SEARCH_AND_ARCHIVE` | Search both tiers and merge results (slower) |
| `FREQUENT_SEARCH_FALLBACK` | Try Archive first, fallback to Frequent Search if no results |

## Metrics Configuration

Coralogix provides a PromQL-compatible endpoint for querying metrics.

**Regional Endpoints** - Choose your region's PromQL endpoint:

- **EU2 (Europe)**: `https://prom-api.eu2.coralogix.com`
- **US1 (USA)**: `https://prom-api.coralogix.com`
- **US2 (USA)**: `https://prom-api.cx498.coralogix.com`
- **AP1 (India)**: `https://prom-api.app.coralogix.in`
- **AP2 (Singapore)**: `https://prom-api.coralogixsg.com`

```yaml-toolset-config
# __HOLMES_HELM_EXTRA__: For Kubernetes deployments, see Advanced Settings below for using environment variables instead of hardcoding the API key
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: "https://prom-api.eu2.coralogix.com"  # Use your region
      healthcheck: "/api/v1/query?query=up"  # Required for Coralogix
      headers:
        token: "<your Coralogix API key>"

      # Coralogix-specific optimizations
      fetch_metadata_with_series_api: true
      fetch_labels_with_labels_api: true
      metrics_labels_time_window_hrs: 72
```

### Advanced Settings

=== "HolmesGPT Helm Chart"

    #### Using Environment Variables

    Instead of hardcoding the API key in values.yaml, use a Kubernetes secret:

    ```bash
    kubectl create secret generic coralogix-secrets \
      --from-literal=CORALOGIX_API_KEY='your-api-key'
    ```

    Then in your `values.yaml`:

    ```yaml
    additionalEnvVars:
      - name: CORALOGIX_API_KEY
        valueFrom:
          secretKeyRef:
            name: coralogix-secrets
            key: CORALOGIX_API_KEY

    toolsets:
      coralogix/logs:
        enabled: true
        config:
          api_key: "{{ env.CORALOGIX_API_KEY }}"
          domain: "eu2.coralogix.com"
          team_hostname: "your-company-name"

      prometheus/metrics:
        enabled: true
        config:
          prometheus_url: "https://prom-api.eu2.coralogix.com"
          healthcheck: "/api/v1/query?query=up"
          headers:
            token: "{{ env.CORALOGIX_API_KEY }}"
          fetch_metadata_with_series_api: true
          fetch_labels_with_labels_api: true
    ```

=== "Robusta Helm Chart"

    #### Using Environment Variables

    For Robusta deployments, create a Kubernetes secret:

    ```bash
    kubectl create secret generic coralogix-secrets \
      --from-literal=CORALOGIX_API_KEY='your-api-key'
    ```

    Then in your `generated_values.yaml`:

    ```yaml
    holmes:
      additionalEnvVars:
        - name: CORALOGIX_API_KEY
          valueFrom:
            secretKeyRef:
              name: coralogix-secrets
              key: CORALOGIX_API_KEY

      toolsets:
        coralogix/logs:
          enabled: true
          config:
            api_key: "{{ env.CORALOGIX_API_KEY }}"
            domain: "eu2.coralogix.com"
            team_hostname: "your-company-name"

        prometheus/metrics:
          enabled: true
          config:
            prometheus_url: "https://prom-api.eu2.coralogix.com"
            healthcheck: "/api/v1/query?query=up"
            headers:
              token: "{{ env.CORALOGIX_API_KEY }}"
            fetch_metadata_with_series_api: true
            fetch_labels_with_labels_api: true
    ```

#### Important Configuration Notes

- **healthcheck**: Must be `/api/v1/query?query=up` (Coralogix doesn't support `-/healthy`)
- **fetch_metadata_with_series_api**: Set to `true` for better compatibility
- **fetch_labels_with_labels_api**: Set to `true` for improved performance
- **metrics_labels_time_window_hrs**: Increase to 72+ hours for better historical analysis
