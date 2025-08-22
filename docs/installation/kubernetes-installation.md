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
        additionalEnvVars:
        - name: OPENAI_API_KEY
          value: "your-openai-api-key"
        # Or load from secret:
        # - name: OPENAI_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: holmes-secrets
        #       key: openai-api-key

        # OPTIONAL: Set default model to avoid specifying it in each request
        # config:
        #   model: "gpt-4o-mini"
        ```

    === "Anthropic"
        ```yaml
        # values.yaml
        additionalEnvVars:
        - name: ANTHROPIC_API_KEY
          value: "your-anthropic-api-key"
        # Or load from secret:
        # - name: ANTHROPIC_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: holmes-secrets
        #       key: anthropic-api-key

        # OPTIONAL: Set default model to avoid specifying it in each request
        # config:
        #   model: "anthropic/claude-3-5-sonnet-20241022"
        ```

    === "Azure OpenAI"
        ```yaml
        # values.yaml
        additionalEnvVars:
        - name: AZURE_API_KEY
          value: "your-azure-api-key"
        - name: AZURE_API_BASE
          value: "https://your-resource.openai.azure.com/"
        - name: AZURE_API_VERSION
          value: "2024-02-15-preview"
        # Or load from secret:
        # - name: AZURE_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: holmes-secrets
        #       key: azure-api-key
        # - name: AZURE_API_BASE
        #   valueFrom:
        #     secretKeyRef:
        #       name: holmes-secrets
        #       key: azure-api-base

        # OPTIONAL: Set default model to avoid specifying it in each request
        # Replace "your-deployment-name" with your actual Azure OpenAI deployment name
        # config:
        #   model: "azure/your-deployment-name"
        ```

    === "Other AI Providers"
        ```yaml
        # values.yaml
        additionalEnvVars:
        # Google Gemini
        - name: GEMINI_API_KEY
          value: "your-gemini-api-key"
        # AWS Bedrock
        - name: AWS_ACCESS_KEY_ID
          value: "your-access-key"
        - name: AWS_SECRET_ACCESS_KEY
          value: "your-secret-key"
        - name: AWS_REGION_NAME
          value: "your-region"
        # Or load from secret:
        # - name: GEMINI_API_KEY
        #   valueFrom:
        #     secretKeyRef:
        #       name: holmes-secrets
        #       key: gemini-api-key

        # OPTIONAL: Set default model to avoid specifying it in each request
        # config:
        #   model: "gemini/gemini-1.5-pro"
        #   # or for AWS Bedrock:
        #   model: "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0"
        ```

        > **Configuration Guide:** Each AI provider requires different environment variables. See the [AI Providers documentation](../ai-providers/index.md) for the specific environment variables needed for your chosen provider, then add them to the `additionalEnvVars` section as shown above. For a complete list of all environment variables, see the [Environment Variables Reference](../reference/environment-variables.md).

3. **Install HolmesGPT:**
   ```bash
   helm install holmesgpt robusta/holmes -f values.yaml
   ```

## Usage

After installation, test the service with a simple API call:

```bash
# Port forward to access the service locally
# Note: Service name is {release-name}-holmes
kubectl port-forward svc/holmesgpt-holmes 8080:80

# If you used a different release name or namespace:
# kubectl port-forward svc/{your-release-name}-holmes 8080:80 -n {your-namespace}

# Test with a basic question
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"ask": "list pods in namespace default?", "model": "gpt-4o-mini"}'

# Without the model parameter, uses config.model from Helm values (defaults to gpt-4o)
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"ask": "list pods in namespace default?"}'
```

> **Note**: Responses may take some time when HolmesGPT needs to gather large amounts of data to answer your question. Streaming APIs are coming soon to stream results.

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

- **[Join our Slack](https://bit.ly/robusta-slack){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
