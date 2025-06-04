# Remote MCP Servers

!!! warning
    Remote MCP servers are in **Tech Preview** stage.

HolmesGPT can integrate with remote MCP servers using SSE mode.
This capability enables HolmesGPT to access external data sources and tools in real time.
This guide provides step-by-step instructions for configuring HolmesGPT to connect with remote MCP servers over SSE.

## Example: MCP server configuration

=== "Helm Chart"

    **Helm Values:**

    ```yaml
    holmes:
      mcp_servers:
        mcp_server_1:
          # human-readable description of the mcp server (this is not seen by the AI model - its just for users)
          description: "Remote mcp server"
          url: "http://example.com:8000/sse"

        mcp_server_2:
          description: "MCP server that runs in my cluster"
          url: "http://<service-name>.<namespace>.svc.cluster.local:<service-port>"
          config:
            headers:
              key: "{{ env.my_mcp_server_key }}" # You can use holmes environment variables as headers for the MCP server requests.
    ```

    Update your Helm values with the provided YAML configuration, then apply the changes with Helm upgrade:

    ```bash
    helm upgrade robusta robusta/robusta --values=generated_values.yaml --set clusterName=<YOUR_CLUSTER_NAME>
    ```
