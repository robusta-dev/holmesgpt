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
   helm repo add robusta https://robusta-charts.storage.googleapis.com
   helm repo update
   ```

2. **Create `values.yaml` file:**

    Create a `values.yaml` file to configure HolmesGPT with your API key:

    === "OpenAI"
        ```yaml
        # values.yaml
        # Image configuration
        image: holmes:0.0.0
        registry: robustadev

        # Logging
        logLevel: INFO

        # Send exception reports to sentry
        enableTelemetry: true

        # API Key configuration
        additionalEnvVars:
        - name: OPENAI_API_KEY
          value: "your-openai-api-key"

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

    === "Anthropic"
        ```yaml
        # values.yaml
        # Image configuration
        image: holmes:0.0.0
        registry: robustadev

        # Logging
        logLevel: INFO

        # Send exception reports to sentry
        enableTelemetry: true

        # API Key configuration
        additionalEnvVars:
        - name: ANTHROPIC_API_KEY
          value: "your-anthropic-api-key"

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

    === "Azure OpenAI"
        ```yaml
        # values.yaml
        # Image configuration
        image: holmes:0.0.0
        registry: robustadev

        # Logging
        logLevel: INFO

        # Send exception reports to sentry
        enableTelemetry: true

        # API Key configuration
        additionalEnvVars:
        - name: AZURE_OPENAI_API_KEY
          value: "your-azure-api-key"
        - name: AZURE_OPENAI_ENDPOINT
          value: "https://your-resource.openai.azure.com/"
        - name: AZURE_OPENAI_API_VERSION
          value: "2024-02-15-preview"

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

3. **Install HolmesGPT:**
   ```bash
   helm install holmesgpt robusta/holmes -f values.yaml
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
helm upgrade holmesgpt robusta/holmes -f values.yaml
```

## Uninstalling

```bash
helm uninstall holmesgpt
```

## Need Help?

- **[Join our Slack](https://robustacommunity.slack.com){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
