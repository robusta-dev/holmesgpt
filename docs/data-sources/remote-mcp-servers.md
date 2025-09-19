# Remote MCP Servers

!!! warning
    Remote MCP servers are in **Tech Preview** stage.

HolmesGPT can integrate with remote MCP servers using either SSE or stdio transports.
This capability enables HolmesGPT to access external data sources and tools in real time
and also to run local/stdio-backed MCP servers directly when desired.
This guide provides step-by-step instructions for configuring HolmesGPT to
connect with remote MCP servers over both SSE and stdio transports.

## Configuration Format

Holmes expects an `mcp_servers` mapping where each key is a logical name for
the MCP server and the value contains metadata plus a transport-specific
`config` block. Minimal top-level fields:

- `description` (string): human-friendly text shown in the UI/configs.
- `llm_instructions` (string, optional): instructions for the LLM about how
  to use the toolset exposed by this MCP server.

Transport selection and supported fields
--------------------------------------
Each MCP entry must indicate the transport type. The recommended pattern is to
set `type` inside a nested `config` mapping, but Holmes also supports a few
backwards-compatible top-level keys (see examples below).

The following two tables describe the supported configuration fields for
each transport. Place fields inside the nested `config` block when possible;
top-level `url`/`command` are accepted for backward compatibility.

### SSE transport configuration

| Field | Location | Description | Required |
|---|---|---|:---:|
| type | `config.type` | Transport indicator; set to `sse` | Recommended |
| url | `config.url` or top-level `url` | Full SSE endpoint (commonly ends with `/sse`) | yes |
| headers | `config.headers` | Optional HTTP headers (e.g. Authorization) | no |
| llm_instructions | top-level | LLM guidance for this toolset | no |
| description | top-level | Human-friendly description | no |

### stdio transport configuration

| Field | Location | Description | Required |
|---|---|---|:---:|
| type | `config.type` | Transport indicator; set to `stdio` | Recommended |
| command | `config.command` or top-level `command` | Executable to run the stdio MCP process | yes |
| args | `config.args` or top-level `args` | Command-line arguments for the process | no |
| env | `config.env` | Environment variables for the launched process | no |
| cwd | `config.cwd` | Working directory for the process | no |
| llm_instructions | top-level | LLM guidance for this toolset | no |
| description | top-level | Human-friendly description | no |

Security notes
--------------
- Avoid placing secrets directly in versioned config files. Prefer environment
  variables or Holmes' secret interpolation for API keys and tokens.
- Holmes strips transport-only and common sensitive fields (for example
  `type` and `key`) from subprocess parameters when constructing `StdioServerParameters`.

## Example: MCP server configuration

```yaml-helm-values
mcp_servers:
  mcp_server_1:
    # human-readable description of the mcp server (this is not seen by the AI model - its just for users)
    description: "Remote mcp server"
    llm_instructions: "This server provides general data access capabilities. Use it when you need to retrieve external information or perform remote operations that aren't covered by other toolsets."
    config:
      url: "http://example.com:8000/sse"
      type: sse

  mcp_server_2:
    description: "MCP server that runs in my cluster"
    llm_instructions: "This is a cluster-local MCP server that provides internal cluster data and operations. Use it for accessing cluster-specific information, internal services, or custom tooling deployed within the Kubernetes environment."
    config:
      type: sse
      url: "http://<service-name>.<namespace>.svc.cluster.local:<service-port>"
      headers:
        key: "{{ env.my_mcp_server_key }}" # You can use holmes environment variables as headers for the MCP server requests.
```

## Example: Working with Stdio MCP servers

MCP itself supports multiple transport mechanisms: stdio, Server-Sent Events (SSE), and
Streamable HTTP. HolmesGPT is compatible with both SSE and stdio transports.
If you already have a stdio-based MCP implementation, HolmesGPT can run it directly
by launching the stdio process (via a configured command/args), or you can wrap it
with a bridge such as Supergateway to expose an SSE endpoint. Both workflows are
documented below.

For this demo we will use:
- [Dynatrace MCP](https://github.com/dynatrace-oss/dynatrace-mcp)
- [Supergateway](https://github.com/supercorp-ai/supergateway) - runs MCP stdio-based servers over SSE

Check out supergatway docs to find out other useful flags.

**See it in action**

<div>
    <a href="https://www.loom.com/share/1b290511b79942c7b1d672a2a4cde105">
      <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/1b290511b79942c7b1d672a2a4cde105-ed4eed3f9d70b125-full-play.gif">
    </a>
</div>

### 1. Run stdio MCP as SSE

=== "Docker"

    This command runs the Dynatrace MCP server locally via Docker using Supergateway to wrap it with SSE support.
    Credentials (e.g., API keys) should be stored in a .env file passed to Docker using --env-file.
    you can change `"npx -y @dynatrace-oss/dynatrace-mcp-server@latest /"` to your specific MCP.

    ```shell
    docker run --env-file .env -it --rm -p  8003:8003 supercorp/supergateway \
    --stdio "npx -y @dynatrace-oss/dynatrace-mcp-server@latest /" \
    --port 8003 \
    --logLevel debug
    ```

    Once the container starts, you should see logs similar to:

    ```shell
    [supergateway] Starting...
    [supergateway] Supergateway is supported by Supermachine (hosted MCPs) - https://supermachine.ai
    [supergateway]   - outputTransport: sse
    [supergateway]   - Headers: (none)
    [supergateway]   - port: 8003
    [supergateway]   - stdio: npx -y @dynatrace-oss/dynatrace-mcp-server@latest /
    [supergateway]   - ssePath: /sse
    [supergateway]   - messagePath: /message
    [supergateway]   - CORS: disabled
    [supergateway]   - Health endpoints: (none)
    [supergateway] Listening on port 8003
    [supergateway] SSE endpoint: http://localhost:8003/sse
    [supergateway] POST messages: http://localhost:8003/message
    ```

=== "Kubernetes Pod"

    This will run dynatrace MCP server as a pod in your cluster.
    credentials are passed as env vars.

    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: dynatrace-mcp
      labels:
        app: dynatrace-mcp
    spec:
      containers:
        - name: supergateway
          image: supercorp/supergateway
          env:
            - name: DT_ENVIRONMENT
              value: https://abcd1234.apps.dynatrace.com
            - name: OAUTH_CLIENT_ID
              value: dt0s02.SAMPLE
            - name: OAUTH_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  name: dynatrace-credentials
                  key: client_secret
          ports:
            - containerPort: 8003
          args:
            - "--stdio"
            - "npx -y @dynatrace-oss/dynatrace-mcp-server@latest /"
            - "--port"
            - "8003"
            - "--logLevel"
            - "debug"
          stdin: true
          tty: true
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: dynatrace-mcp
    spec:
      selector:
        app: dynatrace-mcp
      ports:
        - protocol: TCP
          port: 8003
          targetPort: 8003
      type: ClusterIP
    ```

### 2. Add MCP server to holmes config

With the MCP server running in SSE mode, we need to let HolmesGPT know of the mcp server.
Use this config according to your use case.

**Configuration:**

=== "Holmes CLI"

    Use a config file, and pass it when running cli commands.

    **~/.holmes/config.yaml:**

    ```yaml
    mcp_servers:
      mcp_server_1:
        description: "Dynatrace observability platform. Bring real-time observability data directly into your development workflow."
        llm_instructions: "Use Dynatrace to analyze application performance, infrastructure monitoring, and real-time observability data. Query metrics, traces, and logs to identify performance bottlenecks, errors, and system health issues in your applications and infrastructure."
        config:
          type: "sse"
          url: "http://localhost:8003/sse"

    ```

    You can now use Holmes via the CLI with your configured MCP server. For example:

    ```bash
    holmes ask "Using dynatrace what issues do I have in my cluster?"
    ```

    Alternatively, you can add the `mcp_servers` configurations to **custom_toolset.yaml:***, and run:

    ```bash
    holmes ask -t custom_toolset.yaml "Using dynatrace what issues do I have in my cluster?"
    ```

```yaml-helm-values
mcp_servers:
  mcp_server_1:
    type: "sse"
    description: "Dynatrace observability platform. Bring real-time observability data directly into your development workflow."
    url: "http://dynatrace-mcp.default.svc.cluster.local:8003"
    llm_instructions: "Use Dynatrace to analyze application performance, infrastructure monitoring, and real-time observability data. Query metrics, traces, and logs to identify performance bottlenecks, errors, and system health issues in your applications and infrastructure."
```

After the deployment is complete, you can use HolmesGPT and ask questions like *Using dynatrace what issues do I have in my cluster?*.

Alternatively, if you want Holmes to launch a stdio-backed MCP process directly
(no Supergateway needed), configure the toolset like this:

```yaml
mcp_servers:
  my_stdio_mcp:
    description: "Run a local stdio-based MCP server command"
    command: "/usr/local/bin/my-mcp-server"
    llm_instructions: "This MCP provides local tools and data via stdio transport."
    config:
      type: "stdio"
      args:
        - "--serve"
        - "--port"
        - "0"
      env:
        EXAMPLE_VAR: "value"
```
