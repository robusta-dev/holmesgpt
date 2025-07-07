# Install Helm Chart

Deploy HolmesGPT as a service in your Kubernetes cluster with an HTTP API access.

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

2. **Create Kubernetes Secret with API key:**
   ```bash
   kubectl create secret generic holmes-secrets \
     --from-literal=api-key="your-api-key"
   ```

3. **Create/modify values.yaml:**
   ```yaml
   # values.yaml
   config:
     aiProvider: "openai"
     model: "gpt-4"

   # Reference the secret created above
   secret:
     create: false
     name: "holmes-secrets"
     key: "api-key"
   ```

4. **Install HolmesGPT:**
   ```bash
   helm install holmesgpt holmesgpt/holmes -f values.yaml
   ```

## Configure API Keys via Kubernetes Secret

For different AI providers, create the appropriate secret:

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

- Join our [Slack community](https://robustacommunity.slack.com){:target="_blank"}
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}
