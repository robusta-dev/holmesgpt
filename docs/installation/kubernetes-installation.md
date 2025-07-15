# Install Helm Chart

Deploy HolmesGPT as a service in your Kubernetes cluster with an HTTP API.

!!! warning "When to use the Helm chart?"

    Most users should use the [CLI](cli-installation.md) or [UI/TUI](ui-installation.md) instead. Using the Helm chart is only recommended if you're building a custom integration over an HTTP API.

## Prerequisites

- Kubernetes cluster
- Helm
- kubectl configured to access your cluster
- Supported [AI Provider](../ai-providers/index.md) API key.

## Installation

1. **Add the Helm repository:**
   ```bash
   helm repo add holmesgpt https://robusta-dev.github.io/holmesgpt
   helm repo update
   ```

2. **Load an API Key to HolmesGPT using Kubernetes Secret:**

    === "OpenAI"
        ```bash
        kubectl create secret generic holmes-secrets \
          --from-literal=api-key="your-openai-api-key"
        ```

    === "Anthropic"
        ```bash
        kubectl create secret generic holmes-secrets \
          --from-literal=api-key="your-anthropic-api-key"
        ```

    === "Azure OpenAI"
        ```bash
        kubectl create secret generic holmes-secrets \
          --from-literal=api-key="your-azure-api-key" \
          --from-literal=azure-endpoint="https://your-resource.openai.azure.com/" \
          --from-literal=azure-api-version="2024-02-15-preview"
        ```


3. **Create or modify `values.yaml` to customize HolmesGPT:**

    If you want to change the default configuration, create a `values.yaml` file:
    ```yaml
    # values.yaml
    # Image configuration
    image: holmes:0.0.0
    registry: robustadev

    # Logging
    logLevel: INFO

    # Send exception reports to sentry
    enableTelemetry: true

    # Resource limits
    resources:
      requests:
        cpu: 100m
        memory: 1024Mi
      limits:
        memory: 1024Mi

    # Toolsets configuration
    toolsets:
      kubernetes/core:
        enabled: true
      kubernetes/logs:
        enabled: true
      robusta:
        enabled: true
      internet:
        enabled: true
      prometheus/metrics:
        enabled: true
    ```

4. **Install HolmesGPT:**
   ```bash
   helm install holmesgpt holmesgpt/holmes -f values.yaml
   ```

## Usage

After installation, test the service with a simple API call:

```bash
# Port forward to access the service locally
kubectl port-forward svc/holmesgpt 8080:80

# Test with a basic question
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "what pods are unhealthy and why?"}'
```

For complete API documentation, see the [HTTP API Reference](../reference/http-api.md).


## Upgrading

```bash
helm repo update
helm upgrade holmesgpt holmesgpt/holmes -f values.yaml
```

## Uninstalling

```bash
helm uninstall holmesgpt
```

## Need Help?

- **[Join our Slack](https://robustacommunity.slack.com){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
