# Install Helm Chart

Deploy HolmesGPT as a service in your Kubernetes cluster with HTTP API access.

!!! info "Helm Configuration"
    For all available Helm values and advanced configuration options, see the [Helm Configuration Reference](../reference/helm-configuration.md).

## Prerequisites

- Kubernetes cluster (1.19+)
- Helm 3.x installed
- kubectl configured to access your cluster
- AI provider API key

## Installation with Helm

### Add the Helm Repository

```bash
helm repo add holmesgpt https://robusta-dev.github.io/holmesgpt
helm repo update
```

### Basic Installation

```bash
helm install holmesgpt holmesgpt/holmes
```

### Custom Installation

Create a `values.yaml` file for custom configuration:

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

Install with custom values:

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

#### Ingress (Production)

Configure ingress in your `values.yaml`:

```yaml
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: holmes.your-domain.com
      paths:
        - path: /
          pathType: Prefix
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

## Integration Examples

### Prometheus AlertManager

Configure AlertManager to send alerts to Holmes:

```yaml
# alertmanager.yml
route:
  routes:
    - match:
        severity: critical
      receiver: 'holmes-webhook'

receivers:
  - name: 'holmes-webhook'
    webhook_configs:
      - url: 'http://holmesgpt:80/webhook/alertmanager'
        send_resolved: true
```

### Custom Application Integration

```python
import requests

def investigate_with_holmes(question):
    response = requests.post(
        "http://holmesgpt:80/ask",
        json={"question": question}
    )
    return response.json()

# Example usage
result = investigate_with_holmes("why is my deployment failing?")
print(result["result"])
```

## Troubleshooting

### Common Issues

**Permission Denied**
```bash
kubectl auth can-i get pods --as=system:serviceaccount:default:holmesgpt
```

**API Key Issues**
```bash
kubectl logs deployment/holmesgpt | grep "API key"
```

**Network Connectivity**
```bash
kubectl exec -it deployment/holmesgpt -- curl https://api.openai.com/v1/models
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

## Next Steps

- **[API Keys Setup](../api-keys.md)** - Configure your AI provider
- **[Run Your First Investigation](first-investigation.md)** - Complete walkthrough
- **[Helm Configuration](../reference/helm-configuration.md)** - Advanced settings and custom toolsets

## Need Help?

- Check our [Helm chart documentation](../../helm/)
- Join our [Slack community](https://robustacommunity.slack.com)
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
