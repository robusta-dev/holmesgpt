# Coralogix logs

By enabling this toolset, HolmesGPT will fetch pod logs from [Coralogix](https://coralogix.com/).

--8<-- "snippets/toolsets_that_provide_logging.md"

## Prerequisites

1. A [Coralogix API key](https://coralogix.com/docs/developer-portal/apis/data-query/direct-archive-query-http-api/#api-key) which is assigned the `DataQuerying` permission preset
2. A [Coralogix domain](https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/). For example `eu2.coralogix.com`
3. Your team's [name or hostname](https://coralogix.com/docs/user-guides/account-management/organization-management/create-an-organization/#teams-in-coralogix). For example `your-company-name`

You can deduce the `domain` and `team_hostname` configuration fields by looking at the URL you use to access the Coralogix UI.

For example if you access Coralogix at `https://my-team.app.eu2.coralogix.com/` then the `team_hostname` is `my-team` and the Coralogix `domain` is `eu2.coralogix.com`.

## Configuration

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

## Custom Labels Configuration (Optional)

By default, the Coralogix toolset expects logs to use standard Kubernetes field names. If your Coralogix deployment uses different field names for Kubernetes metadata, you can customize the label mappings.

This is useful when:

- Your log ingestion pipeline uses custom field names
- You have a non-standard Coralogix setup with different metadata fields
- Your Kubernetes logs are structured differently in Coralogix

To find the correct field names, examine your logs in the Coralogix UI and identify how pod names, namespaces, log messages, and timestamps are labeled.

### Example with Custom Labels

```yaml-toolset-config
toolsets:
  coralogix/logs:
    enabled: true
    config:
      api_key: "<your Coralogix API key>"
      domain: "eu2.coralogix.com"
      team_hostname: "your-company-name"
      labels:
        namespace: "kubernetes.namespace_name"     # Default
        pod: "kubernetes.pod_name"                 # Default
        log_message: "userData.logRecord.body"     # Default
        timestamp: "userData.time"                 # Default

  kubernetes/logs:
    enabled: false  # Disable default Kubernetes logging
```

**Label Configuration Fields:**

- `namespace`: Field path for Kubernetes namespace name
- `pod`: Field path for Kubernetes pod name
- `log_message`: Field path for the actual log message content
- `timestamp`: Field path for log timestamp

All label fields are optional and will use the defaults shown above if not specified.

## Logs Retrieval Strategy (Optional)

Coralogix stores logs in two tiers with different performance characteristics:

- **Frequent Search**: Fast queries with limited retention
- **Archive**: Slower queries but longer retention period

You can configure how HolmesGPT retrieves logs using the `logs_retrieval_methodology` setting:

### Available Strategies

- `ARCHIVE_FALLBACK` (default): Try Frequent Search first, fallback to Archive if no results
- `FREQUENT_SEARCH_ONLY`: Only search Frequent Search tier
- `ARCHIVE_ONLY`: Only search Archive tier
- `BOTH_FREQUENT_SEARCH_AND_ARCHIVE`: Search both tiers and merge results
- `FREQUENT_SEARCH_FALLBACK`: Try Archive first, fallback to Frequent Search if no results

### Example Configuration

```yaml-toolset-config
toolsets:
  coralogix/logs:
    enabled: true
    config:
      api_key: "<your Coralogix API key>"
      domain: "eu2.coralogix.com"
      team_hostname: "your-company-name"
      logs_retrieval_methodology: "ARCHIVE_FALLBACK"  # Default
```

**Recommendations:**

- Use `ARCHIVE_FALLBACK` for most cases (balances speed and coverage)
- Use `FREQUENT_SEARCH_ONLY` when you need fastest queries for recent logs
- Use `ARCHIVE_ONLY` when investigating older issues beyond Frequent Search retention
- Use `BOTH_FREQUENT_SEARCH_AND_ARCHIVE` for comprehensive log coverage (slower)

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| coralogix_fetch_logs | Fetch logs from Coralogix for specified pods and time ranges |
