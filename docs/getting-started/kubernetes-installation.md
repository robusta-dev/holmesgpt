# Install Helm Chart

Deploy HolmesGPT as a service in your Kubernetes cluster with HTTP API access.

!!! warning "Helm Configuration"

    Direct API access is generally not recommended unless you are building custom integrations or applications on top of HolmesGPT.

## Prerequisites

- Kubernetes cluster (1.19+)
- Helm 3.x installed
- kubectl configured to access your cluster
- AI provider API key

## Installation

=== "Basic Installation"

    Add the Helm Repository

    ```bash
    helm repo add holmesgpt https://robusta-dev.github.io/holmesgpt
    helm repo update
    ```

    Install HolmesGPT

    ```bash
    helm install holmesgpt holmesgpt/holmes
    ```

=== "Custom Installation"

    Create a `values.yaml` file

    ```yaml
    # values.yaml
    config:
      aiProvider: "openai"
      apiKey: "your-api-key"  # Or use secret
      model: "gpt-4"

    # Use existing secret for API key
    secret:
      create: false
      name: "holmes-secrets"
      key: "api-key"
    ```

    Install with custom values

    ```bash
    helm install holmesgpt holmesgpt/holmes -f values.yaml
    ```

### Using Secrets for API Keys

Create a secret for your AI provider API key:

```bash
kubectl create secret generic holmes-secrets \
  --from-literal=api-key="your-api-key"
```

Reference it in your `values.yaml`:

```yaml
secret:
  create: false
  name: "holmes-secrets"
  key: "api-key"
```

## HTTP API Usage

### Access the Service

#### Port Forward (Development)

```bash
kubectl port-forward svc/holmesgpt 8080:80
```

### API Endpoints

#### Ask Questions

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "what pods are failing in the default namespace?"
  }'
```

#### Investigate Alerts

```bash
curl -X POST http://localhost:8080/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "alert": {
      "name": "HighMemoryUsage",
      "namespace": "production",
      "pod": "web-app-123"
    }
  }'
```

#### Health Check

```bash
curl http://localhost:8080/health
```

### Response Format

```json
{
  "status": "success",
  "result": "Analysis of your Kubernetes cluster shows...",
  "investigation_id": "inv_123456",
  "timestamp": "2024-01-15T10:30:00Z",
  "toolsets_used": ["kubernetes", "prometheus"],
  "recommendations": [
    "Scale up the deployment",
    "Check resource limits"
  ]
}
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

- Check our [Helm chart documentation](../../helm/)
- Join our [Slack community](https://robustacommunity.slack.com)
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
