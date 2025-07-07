# Helm Configuration

Complete reference for configuring HolmesGPT with Helm values.

## Basic Configuration

```yaml
# values.yaml
config:
  # AI Provider Settings
  aiProvider: "openai"  # "openai", "anthropic", "bedrock", "vertex"
  model: "gpt-4"
  maxTokens: 2000
  temperature: 0.1

# API Key Configuration
secret:
  create: true
  name: "holmes-secrets"
  key: "api-key"
  value: "your-api-key"

# Service Configuration
service:
  type: ClusterIP
  port: 80
  targetPort: 8080

# Resource Limits
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

# RBAC
rbac:
  create: true
  serviceAccountName: "holmesgpt"

# Ingress
ingress:
  enabled: false
  className: "nginx"
  annotations: {}
  hosts:
    - host: holmes.example.com
      paths:
        - path: /
          pathType: Prefix
  tls: []
```

## AI Provider Configuration

### OpenAI

```yaml
config:
  aiProvider: "openai"
  model: "gpt-4"
  apiEndpoint: "https://api.openai.com/v1"

secret:
  create: true
  value: "sk-..."
```

### Anthropic

```yaml
config:
  aiProvider: "anthropic"
  model: "claude-3-sonnet-20240229"
  apiEndpoint: "https://api.anthropic.com"

secret:
  create: true
  value: "sk-ant-..."
```

### AWS Bedrock

```yaml
config:
  aiProvider: "bedrock"
  model: "anthropic.claude-3-sonnet-20240229-v1:0"
  region: "us-east-1"

# Use IAM roles or provide credentials
aws:
  accessKeyId: "AKIA..."
  secretAccessKey: "..."
  sessionToken: ""  # Optional
```

### Google Vertex AI

```yaml
config:
  aiProvider: "vertex"
  model: "gemini-pro"
  project: "your-project-id"
  location: "us-central1"

# Provide service account key
gcp:
  serviceAccountKey: |
    {
      "type": "service_account",
      ...
    }
```

## Toolset Configuration

```yaml
toolsets:
  - name: "kubernetes"
    enabled: true
    config: {}

  - name: "prometheus"
    enabled: true
    config:
      url: "http://prometheus:9090"
      timeout: "30s"

  - name: "grafana"
    enabled: true
    config:
      url: "http://grafana:3000"
      username: "admin"
      password: "admin"

  - name: "loki"
    enabled: true
    config:
      url: "http://loki:3100"

  - name: "tempo"
    enabled: true
    config:
      url: "http://tempo:3200"
```

## Security Configuration

### RBAC Permissions

```yaml
rbac:
  create: true

# Custom ClusterRole rules
rbacRules:
  - apiGroups: [""]
    resources: ["pods", "services", "events", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

### Network Policies

```yaml
networkPolicy:
  enabled: true
  ingress:
    - from:
      - namespaceSelector:
          matchLabels:
            name: monitoring
      ports:
      - protocol: TCP
        port: 8080
  egress:
    - to: []
      ports:
      - protocol: TCP
        port: 443  # HTTPS to AI providers
```

### Pod Security Context

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  runAsGroup: 1001
  fsGroup: 1001

containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
    - ALL
```

## Monitoring Configuration

```yaml
monitoring:
  enabled: true

# Prometheus metrics
metrics:
  enabled: true
  port: 9090
  path: /metrics

# Service Monitor for Prometheus Operator
serviceMonitor:
  enabled: true
  namespace: monitoring
  labels:
    release: prometheus

# Grafana Dashboard
grafanaDashboard:
  enabled: true
  namespace: monitoring
```

## Scaling Configuration

### Horizontal Pod Autoscaler

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
```

### Vertical Pod Autoscaler

```yaml
verticalPodAutoscaler:
  enabled: true
  updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: holmesgpt
      maxAllowed:
        cpu: 1
        memory: 1Gi
```

## Storage Configuration

```yaml
persistence:
  enabled: true
  storageClass: "standard"
  size: "10Gi"
  accessMode: "ReadWriteOnce"

# Volume mounts
volumes:
  - name: config
    configMap:
      name: holmes-config
  - name: cache
    emptyDir: {}

volumeMounts:
  - name: config
    mountPath: /app/config
    readOnly: true
  - name: cache
    mountPath: /app/cache
```

## Environment Variables

```yaml
env:
  - name: HOLMES_LOG_LEVEL
    value: "INFO"
  - name: HOLMES_MAX_INVESTIGATIONS
    value: "10"
  - name: HOLMES_CACHE_TTL
    value: "3600"
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: holmes-secrets
        key: api-key
```

## Advanced Configuration

### Multi-Tenant Setup

```yaml
# Namespace isolation
namespaceSelector:
  matchLabels:
    holmes-enabled: "true"

# Per-tenant configuration
tenants:
  - name: "team-a"
    namespace: "team-a"
    aiProvider: "openai"
    apiKey: "sk-team-a-key"
  - name: "team-b"
    namespace: "team-b"
    aiProvider: "anthropic"
    apiKey: "sk-team-b-key"
```

### Custom Toolsets

```yaml
customToolsets:
  - name: "custom-monitoring"
    image: "myregistry/custom-toolset:latest"
    config:
      endpoint: "https://my-monitoring.com"
      apiKey: "secret"
```

## Production Recommendations

```yaml
# Production values.yaml
replicaCount: 3

resources:
  limits:
    cpu: 1
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 20

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
  tls:
    - secretName: holmes-tls
      hosts:
        - holmes.company.com

monitoring:
  enabled: true

networkPolicy:
  enabled: true

securityContext:
  runAsNonRoot: true
  runAsUser: 1001
```

## Configuration Validation

Validate your configuration before deployment:

```bash
# Dry run
helm install holmesgpt holmesgpt/holmes -f values.yaml --dry-run

# Template output
helm template holmesgpt holmesgpt/holmes -f values.yaml

# Validate with kubeval
helm template holmesgpt holmesgpt/holmes -f values.yaml | kubeval
```

## Troubleshooting Configuration

Common configuration issues:

1. **Invalid YAML syntax**
   ```bash
   yamllint values.yaml
   ```

2. **Missing required values**
   ```bash
   helm lint -f values.yaml
   ```

3. **RBAC permission issues**
   ```bash
   kubectl auth can-i get pods --as=system:serviceaccount:default:holmesgpt
   ```

For more configuration examples, see the [examples directory](https://github.com/robusta-dev/holmesgpt/tree/main/helm/examples){:target="_blank"} in our repository.
