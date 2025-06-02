# Kubernetes Installation

Deploy HolmesGPT as a service in your Kubernetes cluster with HTTP API access.

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

# Service configuration
service:
  type: ClusterIP
  port: 80

# Ingress configuration
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: holmes.your-domain.com
      paths:
        - path: /
          pathType: Prefix

# Resource limits
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

# RBAC permissions
rbac:
  create: true

# Custom toolsets
toolsets:
  - name: "prometheus"
    enabled: true
    config:
      url: "http://prometheus:9090"
  - name: "grafana"
    enabled: true
    config:
      url: "http://grafana:3000"
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

Configure ingress in your `values.yaml` (see example above).

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

### Grafana Integration

Add Holmes as a data source in Grafana:

```bash
curl -X POST http://grafana:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "HolmesGPT",
    "type": "holmesgpt",
    "url": "http://holmesgpt:80",
    "access": "proxy"
  }'
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

## Configuration Options

### Environment Variables

Set these in your Helm values:

```yaml
env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: api-key
  - name: HOLMES_LOG_LEVEL
    value: "INFO"
  - name: HOLMES_MAX_INVESTIGATIONS
    value: "10"
```

### Volume Mounts

Mount custom configurations:

```yaml
volumes:
  - name: custom-config
    configMap:
      name: holmes-config

volumeMounts:
  - name: custom-config
    mountPath: /app/config
    readOnly: true
```

## Monitoring and Observability

### Metrics

Holmes exposes Prometheus metrics at `/metrics`:

```bash
curl http://localhost:8080/metrics
```

Key metrics:
- `holmes_investigations_total`
- `holmes_investigation_duration_seconds`
- `holmes_toolset_executions_total`
- `holmes_errors_total`

### Logs

View Holmes logs:

```bash
kubectl logs -f deployment/holmesgpt
```

### Health Checks

Configure readiness and liveness probes:

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 60
  periodSeconds: 30
```

## Security Considerations

### RBAC Permissions

Holmes requires these Kubernetes permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: holmes-reader
rules:
- apiGroups: [""]
  resources: ["pods", "services", "events", "nodes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["metrics.k8s.io"]
  resources: ["pods", "nodes"]
  verbs: ["get", "list"]
```

### Network Policies

Restrict network access:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: holmes-netpol
spec:
  podSelector:
    matchLabels:
      app: holmesgpt
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS to AI providers
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   kubectl auth can-i get pods --as=system:serviceaccount:default:holmesgpt
   ```

2. **API Key Issues**
   ```bash
   kubectl logs deployment/holmesgpt | grep "API key"
   ```

3. **Network Connectivity**
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
