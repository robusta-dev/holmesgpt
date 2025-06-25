# ServiceNow

By enabling this toolset, HolmesGPT will be able to interact with ServiceNow for ticket management, incident tracking, and accessing knowledge base articles during investigations.

## Prerequisites

1. ServiceNow instance URL
2. ServiceNow username and password or API token
3. Appropriate ServiceNow roles and permissions

## Configuration

=== "Holmes CLI"

    First, set the following environment variables:

    ```bash
    export SERVICENOW_INSTANCE="<your servicenow instance url>"
    export SERVICENOW_USERNAME="<your servicenow username>"
    export SERVICENOW_PASSWORD="<your servicenow password>"
    ```

    Then add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      servicenow/tickets:
        enabled: true
        config:
          verify_ssl: true
          timeout: 30
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      additionalEnvVars:
        - name: SERVICENOW_INSTANCE
          value: "<your servicenow instance url>"
        - name: SERVICENOW_USERNAME
          value: "<your servicenow username>"
        - name: SERVICENOW_PASSWORD
          value: "<your servicenow password>"
      toolsets:
        servicenow/tickets:
          enabled: true
          config:
            verify_ssl: true
            timeout: 30
    ```

## Advanced Configuration

You can customize ServiceNow integration settings:

```yaml
toolsets:
  servicenow/tickets:
    enabled: true
    config:
      verify_ssl: true
      timeout: 30  # Request timeout in seconds
      max_results: 100  # Maximum number of tickets to fetch
      default_table: "incident"  # Default ServiceNow table to query
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| servicenow_create_incident | Create a new incident ticket in ServiceNow |
| servicenow_get_incident | Get details of a specific incident |
| servicenow_search_incidents | Search for incidents based on criteria |
| servicenow_update_incident | Update an existing incident |
| servicenow_get_knowledge_base | Search ServiceNow knowledge base articles |
| servicenow_create_change_request | Create a change request ticket |
