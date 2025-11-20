# Remote MCP Servers

!!! warning
    Remote MCP servers are in **Tech Preview** stage.

!!! note "Configuration Change"
    **The MCP server configuration format has been updated.** The `url` field must now be specified inside the `config` section instead of at the top level. The old format (with `url` at the top level) is still supported for backward compatibility but will log a migration warning. Please update your configurations to use the new format.

!!! warning "SSE Mode Deprecation"
    The SSE (Server-Sent Events) transport mode for MCP is being deprecated across the MCP ecosystem.
    **We strongly recommend using `streamable-http` mode** for new MCP server integrations.
    SSE mode support is maintained for backward compatibility but may be removed in future versions.

HolmesGPT can integrate with remote MCP servers using **stdio**, **streamable-http** (recommended), or **SSE** (deprecated) transport modes.
This capability enables HolmesGPT to access external data sources and tools in real time.
This guide provides step-by-step instructions for configuring HolmesGPT to connect with remote MCP servers.

!!! note "Configuration Structure"
    **`mcp_servers` is a separate top-level key** in the configuration file, alongside `toolsets`. Both can coexist in the same config file:

    ```yaml
    toolsets:
      my_custom_toolset:
        # ... toolset configuration

    mcp_servers:
      my_mcp_server:
        # ... MCP server configuration
    ```

    Internally, MCP servers are treated as toolsets with `type: MCP` and are merged with other toolsets. This means MCP servers appear alongside regular toolsets in HolmesGPT's toolset list and can be enabled/disabled like any other toolset.

## Transport Modes

HolmesGPT supports three MCP transport modes:

1. **`stdio`**: Direct process communication using standard input/output. Ideal for running MCP servers as subprocesses within the same container or pod.
2. **`streamable-http`** (Recommended): Modern transport mode that uses HTTP POST requests with JSON responses. This is the preferred mode for new integrations.
3. **`sse`** (Deprecated): Legacy transport mode using Server-Sent Events. Maintained for backward compatibility only.

### Configuring Transport Mode

The transport mode and URL are specified in the `config` section of your MCP server configuration:

```yaml
mcp_servers:
  my_server:
    description: "My MCP server"
    config:
      url: "http://example.com:8000/mcp/messages"  # Path depends on your server (could be /mcp, /mcp/messages, etc.)
      mode: streamable-http  # Explicitly set the mode
      headers:
        Authorization: "Bearer token123"
```

!!! note "URL Path Variability"
    Different MCP servers may use different endpoint paths. Common examples include:
    - `/mcp/messages` - Used by some servers
    - `/mcp` - Used by other servers (e.g., Azure Kubernetes MCP)
    - Custom paths as defined by your server

    The streamable-http client automatically handles the protocol regardless of the path. Consult your MCP server's documentation to determine the correct endpoint URL.

If no mode is specified, the system defaults to `sse` for backward compatibility. However, **this default will be deprecated in the future**, and **you should explicitly set `mode: streamable-http` or `mode: sse`** for new and old servers.

### URL Format

- **Streamable-HTTP**: URL should point to the MCP server endpoint. The exact path depends on your server configuration:
  - Some servers use `/mcp/messages` (e.g., `http://example.com:8000/mcp/messages`)
  - Others use `/mcp` (e.g., `http://example.com:3333/mcp`)
  - The streamable-http client automatically handles POST requests and responses at the provided URL
  - Check your MCP server documentation for the correct endpoint path
- **SSE**: URL should end with `/sse` (e.g., `http://example.com:8000/sse`). If the URL doesn't end with `/sse`, HolmesGPT will automatically append it.
- **Stdio**: No URL is required. Instead, specify a `command` to execute the MCP server process, along with optional `args` and `env` variables.

## Example: MCP server configuration

### Streamable-HTTP (Recommended)

```yaml-helm-values
mcp_servers:
  mcp_server_1:
    # human-readable description of the mcp server (this is not seen by the AI model - its just for users)
    description: "Remote mcp server using streamable-http"
    config:
      url: "http://example.com:8000/mcp/messages"  # Path may vary: /mcp, /mcp/messages, or custom path
      mode: streamable-http  # Explicitly set the preferred mode
      headers:
        Authorization: "Bearer {{ env.my_mcp_server_key }}"  # You can use holmes environment variables as headers
    llm_instructions: "This server provides general data access capabilities. Use it when you need to retrieve external information or perform remote operations that aren't covered by other toolsets."
```

### SSE (Deprecated - Use Only for Legacy Servers)

```yaml-helm-values
mcp_servers:
  mcp_server_legacy:
    description: "Legacy MCP server using SSE (deprecated)"
    config:
      url: "http://example.com:8000/sse"  # Must end with /sse
      mode: sse  # Explicitly set, though this is deprecated
    llm_instructions: "Legacy server using deprecated SSE transport."

  mcp_server_2:
    description: "MCP server that runs in my cluster"
    config:
      url: "http://<service-name>.<namespace>.svc.cluster.local:<service-port>/sse"  # SSE endpoint must end with /sse
      mode: sse  # Explicitly set SSE mode (deprecated)
      headers:
        key: "{{ env.my_mcp_server_key }}"  # You can use holmes environment variables as headers for the MCP server requests.
    llm_instructions: "This is a cluster-local MCP server that provides internal cluster data and operations. Use it for accessing cluster-specific information, internal services, or custom tooling deployed within the Kubernetes environment."
```

### Stdio

Stdio mode allows HolmesGPT to run MCP servers directly as subprocesses, communicating via standard input/output. This is useful when you want to run MCP servers within the same container or pod as HolmesGPT.

**Key Configuration Fields:**

- `mode`: Must be set to `stdio`
- `command`: The command to execute (e.g., `python3`, `node`, `/usr/bin/my-mcp-server`)
- `args`: (Optional) List of arguments to pass to the command
- `env`: (Optional) Dictionary of environment variables to set for the process

**Configuration Examples:**

=== "Holmes CLI"

    Use a config file, and pass it when running CLI commands.

    **custom_toolset.yaml:**

    ```yaml
    mcp_servers:
      stdio_example:
        description: "Custom stdio MCP server running as a subprocess"
        config:
          mode: stdio
          command: "python3"
          args:
            - "./stdio_server.py"
          env:
            CUSTOM_VAR: "value"
        llm_instructions: "Use this MCP server to access custom tools and capabilities provided by the stdio server process. Refer to the available tools from this server when needed."
    ```

    **Note:** Ensure that the required Python packages (like `mcp` and `fastmcp`) are installed in your Python environment.

    You can now use Holmes via the CLI with your configured stdio MCP server. For example:

    ```bash
    holmes ask -t custom_toolset.yaml "Run my mcp-server tools"
    ```

=== "Holmes Helm Chart"

    !!! warning "Stdio Limitations in Helm Deployments"
        **Stdio mode is not recommended for running MCP servers directly in the Holmes container** due to limitations of the Holmes container image. Your stdio MCP server may have dependencies (Python packages, system libraries, etc.) that are not available in the Holmes image, which will cause the server to fail.

    **Recommended Approach: Run stdio MCP servers as a SSE MCP server pod**

    For in-cluster deployments, run your stdio MCP server in its own container using Supergateway to convert it to SSE, then connect Holmes to it.

    **First, create a custom Docker image** that contains your stdio MCP server and all its required dependencies. Use the Supergateway base image pattern:

    ```dockerfile
    FROM supercorp/supergateway:latest

    USER root
    # Add needed files and dependencies here
    # Example: RUN apk add --no-cache python3 py3-pip
    # Example: RUN pip3 install --no-cache-dir --break-system-packages your-mcp-server-package
    USER node

    EXPOSE 8000
    # Replace "YOUR MCP SERVER COMMAND HERE" with your actual MCP server command
    # Examples:
    #   CMD ["--port", "8000", "--stdio", "python3", "-m", "your_mcp_server_module"]
    #   CMD ["--port", "8000", "--stdio", "python3", "/app/stdio_server.py"]
    #   CMD ["--port", "8000", "--stdio", "npx", "-y", "@your-org/your-mcp-server@latest"]
    CMD ["--port", "8000", "--stdio", "YOUR MCP SERVER COMMAND HERE"]
    ```

    Build and push your image.

    **Deploy the MCP server in your cluster:**

    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: my-mcp-server
      labels:
        app: my-mcp-server
    spec:
      containers:
        - name: supergateway
          image: your-registry/your-mcp-server:latest
          ports:
            - containerPort: 8000
          args:
            - "--stdio"
            # Replace "YOUR MCP SERVER COMMAND HERE" with your actual MCP server command
            # Examples: "python3 -m your_mcp_server_module", "python3 /app/stdio_server.py", "npx -y @your-org/your-mcp-server@latest"
            - "YOUR MCP SERVER COMMAND HERE"
            - "--port"
            - "8000"
            - "--logLevel"
            - "debug"
          stdin: true
          tty: true
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: my-mcp-server
    spec:
      selector:
        app: my-mcp-server
      ports:
        - protocol: TCP
          port: 8000
          targetPort: 8000
      type: ClusterIP
    ```

    **Connect Holmes to the MCP server:**

    After deploying the MCP server, configure Holmes to connect to it via SSE:

    ```yaml
    mcp_servers:
      my_mcp_server:
        description: "My custom MCP server running in-cluster"
        config:
          url: "http://my-mcp-server.default.svc.cluster.local:8000/sse"
          mode: sse
        llm_instructions: "Use this MCP server to access custom tools and capabilities. Refer to the available tools from this server when needed."
    ```

    Apply the configuration:

    ```bash
    helm upgrade holmes holmes/holmes --values=values.yaml
    ```

=== "Robusta Helm Chart"

    !!! warning "Stdio Limitations in Helm Deployments"
        **Stdio mode is not recommended for running MCP servers directly in the Holmes container** due to limitations of the Holmes container image. Your stdio MCP server may have dependencies (Python packages, system libraries, etc.) that are not available in the Holmes image, which will cause the server to fail.

    **Recommended Approach: Run stdio MCP servers as a SSE MCP server pod**

    For in-cluster deployments, run your stdio MCP server in its own container using Supergateway to convert it to SSE, then connect Holmes to it.

    **First, create a custom Docker image** that contains your stdio MCP server and all its required dependencies. Use the Supergateway base image pattern:

    ```dockerfile
    FROM supercorp/supergateway:latest

    USER root
    # Add needed files and dependencies here
    # Example: RUN apk add --no-cache python3 py3-pip
    # Example: RUN pip3 install --no-cache-dir --break-system-packages your-mcp-server-package
    USER node

    EXPOSE 8000
    # Replace "YOUR MCP SERVER COMMAND HERE" with your actual MCP server command
    # Examples:
    #   CMD ["--port", "8000", "--stdio", "python3", "-m", "your_mcp_server_module"]
    #   CMD ["--port", "8000", "--stdio", "python3", "/app/stdio_server.py"]
    #   CMD ["--port", "8000", "--stdio", "npx", "-y", "@your-org/your-mcp-server@latest"]
    CMD ["--port", "8000", "--stdio", "YOUR MCP SERVER COMMAND HERE"]
    ```

    Build and push your image.

    **Deploy the MCP server in your cluster:**

    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: my-mcp-server
      labels:
        app: my-mcp-server
    spec:
      containers:
        - name: supergateway
          image: your-registry/your-mcp-server:latest
          ports:
            - containerPort: 8000
          args:
            - "--stdio"
            # Replace "YOUR MCP SERVER COMMAND HERE" with your actual MCP server command
            # Examples: "python3 -m your_mcp_server_module", "python3 /app/stdio_server.py", "npx -y @your-org/your-mcp-server@latest"
            - "YOUR MCP SERVER COMMAND HERE"
            - "--port"
            - "8000"
            - "--logLevel"
            - "debug"
          stdin: true
          tty: true
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: my-mcp-server
    spec:
      selector:
        app: my-mcp-server
      ports:
        - protocol: TCP
          port: 8000
          targetPort: 8000
      type: ClusterIP
    ```

    Apply the configuration:

    ```bash
    helm upgrade robusta robusta/robusta --values=generated_values.yaml --set clusterName=<YOUR_CLUSTER_NAME>
    ```

## Example: Working with Stdio MCP servers via Supergateway

While HolmesGPT now supports **stdio** mode directly (see above), you may still want to use Supergateway in some scenarios:
- When you need to expose a stdio-based MCP server as an HTTP endpoint for multiple clients
- When you want to run the MCP server in a separate pod/container for better isolation
- When integrating with existing stdio-based MCP servers that you prefer to keep separate

Tools like Supergateway can act as a bridge by converting stdio-based MCPs into streamable-http or SSE-compatible endpoints.

!!! tip "Prefer Streamable-HTTP"
    When using Supergateway or similar tools, configure them to use `streamable-http` mode instead of SSE for better compatibility and future-proofing.

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

    **custom_toolset.yaml:**

    ```yaml
    mcp_servers:
      mcp_server_1:
        description: "Dynatrace observability platform. Bring real-time observability data directly into your development workflow."
        config:
          url: "http://localhost:8003/sse"
        llm_instructions: "Use Dynatrace to analyze application performance, infrastructure monitoring, and real-time observability data. Query metrics, traces, and logs to identify performance bottlenecks, errors, and system health issues in your applications and infrastructure."
    ```

    You can now use Holmes via the CLI with your configured MCP server. For example:

    ```bash
    holmes ask -t custom_toolset.yaml  "Using dynatrace what issues do I have in my cluster?"
    ```

    Alternatively, you can add the `mcp_servers` configurations to ** ~/.holmes/config.yaml**, and run:

    ```bash
    holmes ask "Using dynatrace what issues do I have in my cluster?"
    ```

```yaml-helm-values
mcp_servers:
  mcp_server_1:
    description: "Dynatrace observability platform. Bring real-time observability data directly into your development workflow."
    config:
      url: "http://dynatrace-mcp.default.svc.cluster.local:8003"
    llm_instructions: "Use Dynatrace to analyze application performance, infrastructure monitoring, and real-time observability data. Query metrics, traces, and logs to identify performance bottlenecks, errors, and system health issues in your applications and infrastructure."
```

After the deployment is complete, you can use HolmesGPT and ask questions like *Using dynatrace what issues do I have in my cluster?*.
