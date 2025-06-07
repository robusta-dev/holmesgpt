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

```yaml
holmes:
  additionalEnvVars:
  - name: NOTION_AUTH
    valueFrom:
      secretKeyRef:
        name: notion-secret-key
        key: NOTION_SECRET_HERE
    toolsets:
        notion:
            enabled: true
            config:
              additional_headers:
                Authorization: Bearer {{ env.NOTION_AUTH }}
```

## Capabilities

| Tool Name | Description |
|-----------|-------------|
| fetch_notion_webpage | Fetch a notion webpage. Use this to fetch notion runbooks if they are present before starting your investigation |
