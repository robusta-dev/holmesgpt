# Coralogix logs

By enabling this toolset, HolmesGPT will fetch pod logs from [Coralogix](https://coralogix.com/).

You **should** enable this toolset to replace the default Kubernetes logs toolset if all your kubernetes pod logs are consolidated inside Coralogix. It will make it easier for HolmesGPT to fetch incident logs, including the ability to precisely consult past logs.

!!! warning "Logging Toolsets"
    Only one logging toolset should be enabled at a time. If you enable this toolset, disable the default `kubernetes/logs` toolset.

## Prerequisites

1. A [Coralogix API key](https://coralogix.com/docs/developer-portal/apis/data-query/direct-archive-query-http-api/#api-key) which is assigned the `DataQuerying` permission preset
2. A [Coralogix domain](https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/). For example `eu2.coralogix.com`
3. Your team's [name or hostname](https://coralogix.com/docs/user-guides/account-management/organization-management/create-an-organization/#teams-in-coralogix). For example `your-company-name`

You can deduct the `domain` and `team_hostname` configuration fields by looking at the URL you use to access the Coralogix UI.

For example if you access coralogix at `https://my-team.app.eu2.coralogix.com/` then the `team_hostname` is `my-team` and the coralogix `domain` is `eu2.coralogix.com`.

## Configuration

=== "Holmes CLI"

    Add the following to **~/.holmes/config.yaml**, creating the file if it doesn't exist:

    ```yaml
    toolsets:
      coralogix/logs:
        enabled: true
        config:
          api_key: "<your coralogix API key>"
          domain: "eu2.coralogix.com"
          team_hostname: "your-company-name"

      kubernetes/logs:
        enabled: false  # Disable default Kubernetes logging
    ```

=== "Robusta Helm Chart"

    ```yaml
    holmes:
      toolsets:
        coralogix/logs:
          enabled: true
          config:
            api_key: "<your coralogix API key>"
            domain: "eu2.coralogix.com"
            team_hostname: "your-company-name"

        kubernetes/logs:
          enabled: false  # Disable default Kubernetes logging
    ```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| coralogix_fetch_logs | Fetch logs from Coralogix for specified pods and time ranges |
