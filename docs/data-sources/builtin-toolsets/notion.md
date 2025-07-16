# Notion

Notion Integration for HolmesGPT

Enabling this toolset allows HolmesGPT to fetch pages from Notion, making it useful when providing Notion-based runbooks.

## Setup Instructions

1. **Create a Webhook Integration**

    - Go to the Notion Developer Portal.
    - Create a new integration with **read content** capabilities.

2. **Grant Access to Pages**

    - Open the desired Notion page.
    - Click the three dots in the top right.
    - Select **Connections** and add your integration.

3. **Configure Authentication**

    - Retrieve the **Internal Integration Secret** from Notion.
    - Create a Kubernetes secret in your cluster with this key.
    - Configure the `NOTION_AUTH` environment variable.

## Configuration

=== "Holmes CLI"

    First, set the environment variable:
    ```bash
    export NOTION_AUTH="<your Notion integration secret>"
    ```

    Then add the following to **~/.holmes/config.yaml**. Create the file if it doesn't exist:
    ```yaml
    toolsets:
        notion:
            enabled: true
    ```

    --8<-- "snippets/toolset_refresh_warning.md"

=== "Robusta Helm Chart"

    ```yaml
    holmes:
        additionalEnvVars:
            - name: NOTION_AUTH
              value: "<your Notion integration secret>"
        toolsets:
            notion:
                enabled: true
                config:
                    additional_headers:
                        Authorization: Bearer {{ env.NOTION_AUTH }}
    ```

    --8<-- "snippets/helm_upgrade_command.md"

## Capabilities

--8<-- "snippets/toolset_capabilities_intro.md"

| Tool Name | Description |
|-----------|-------------|
| fetch_notion_webpage | Fetch a Notion webpage. Use this to fetch Notion runbooks if they are present before starting your investigation |
