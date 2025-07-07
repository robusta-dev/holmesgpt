# Troubleshooting

Common issues and solutions for HolmesGPT deployment and operation.

## Installation Issues

### Helm Installation Failed

**Problem:** Helm install command fails with validation errors.

**Solution:**
```bash
# Check Helm version (requires 3.x)
helm version

# Verify repository is added
helm repo list | grep holmesgpt

# Update repository
helm repo update

# Check available chart versions
helm search repo holmesgpt
```

### Pod Not Starting

**Problem:** HolmesGPT pod stuck in `Pending` or `CrashLoopBackOff` state.

**Diagnosis:**
```bash
# Check pod status
kubectl get pods -l app=holmesgpt

# View pod events
kubectl describe pod <pod-name>

# Check logs
kubectl logs <pod-name>
```

**Common causes:**
- Insufficient resources
- Missing API key
- RBAC permission issues
- Image pull failures

## API Key Issues

### Invalid API Key Error

**Problem:** `Invalid API key` errors in logs.

**Solution:**
```bash
# Verify secret exists
kubectl get secret holmes-secrets

# Check secret content (base64 encoded)
kubectl get secret holmes-secrets -o yaml

# Update API key
kubectl patch secret holmes-secrets -p '{"data":{"api-key":"<base64-encoded-key>"}}'

# Restart deployment
kubectl rollout restart deployment holmesgpt
```

### API Rate Limits

**Problem:** `Rate limit exceeded` errors.

**Solution:**
```bash
# Check current usage in logs
kubectl logs -l app=holmesgpt | grep "rate limit"

# Configure rate limiting in values.yaml
cat <<EOF > values.yaml
config:
  rateLimit:
    requestsPerMinute: 60
    burstLimit: 10
EOF

helm upgrade holmesgpt holmesgpt/holmes -f values.yaml
```

## Permission Issues

### RBAC Errors

**Problem:** `Forbidden` errors when accessing Kubernetes resources.

**Diagnosis:**
```bash
# Check service account
kubectl get serviceaccount holmesgpt

# Verify cluster role binding
kubectl get clusterrolebinding | grep holmesgpt

# Test permissions
kubectl auth can-i get pods --as=system:serviceaccount:default:holmesgpt
```

**Solution:**
```yaml
# values.yaml
rbac:
  create: true

# Additional permissions if needed
rbacRules:
  - apiGroups: [""]
    resources: ["pods", "services", "events", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
```

### Namespace Access Issues

**Problem:** Cannot access resources in specific namespaces.

**Solution:**
```bash
# Create role binding for specific namespace
kubectl create rolebinding holmesgpt-reader \
  --clusterrole=holmesgpt-reader \
  --serviceaccount=default:holmesgpt \
  --namespace=production
```

## Network Connectivity Issues

### Cannot Reach AI Provider

**Problem:** `Connection timeout` or `DNS resolution failed` errors.

**Diagnosis:**
```bash
# Test from pod
kubectl exec -it <pod-name> -- curl -I https://api.openai.com

# Check DNS resolution
kubectl exec -it <pod-name> -- nslookup api.openai.com

# Verify network policies
kubectl get networkpolicies
```

**Solution:**
```yaml
# Network policy allowing egress to AI providers
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: holmesgpt-egress
spec:
  podSelector:
    matchLabels:
      app: holmesgpt
  policyTypes:
  - Egress
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443
```

### Internal Service Communication

**Problem:** Cannot reach internal services (Prometheus, Grafana, etc.).

**Solution:**
```bash
# Verify service endpoints
kubectl get endpoints prometheus

# Test connectivity
kubectl exec -it <pod-name> -- curl http://prometheus:9090/api/v1/query

# Check service discovery
kubectl get services -A | grep prometheus
```

## Performance Issues

### Slow Response Times

**Problem:** Investigations taking too long to complete.

**Diagnosis:**
```bash
# Check resource usage
kubectl top pods -l app=holmesgpt

# Review metrics
kubectl port-forward svc/holmesgpt 9090:9090
curl http://localhost:9090/metrics | grep holmes_
```

**Solutions:**

1. **Increase resources:**
```yaml
resources:
  limits:
    cpu: 1
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi
```

2. **Optimize AI provider settings:**
```yaml
config:
  maxTokens: 1000  # Reduce token limit
  temperature: 0   # Faster, more deterministic responses
  timeout: 30s     # Set reasonable timeout
```

3. **Enable caching:**
```yaml
config:
  cache:
    enabled: true
    ttl: 3600
```

### High Memory Usage

**Problem:** Pod consuming excessive memory.

**Solution:**
```bash
# Monitor memory usage
kubectl top pods -l app=holmesgpt --containers

# Check for memory leaks in logs
kubectl logs -l app=holmesgpt | grep -i "memory\|oom"

# Set memory limits
helm upgrade holmesgpt holmesgpt/holmes --set resources.limits.memory=512Mi
```

## Investigation Issues

### No Results Returned

**Problem:** HolmesGPT returns empty or minimal results.

**Diagnosis:**
```bash
# Check toolset configuration
kubectl logs -l app=holmesgpt | grep "toolset"

# Verify data source connectivity
kubectl exec -it <pod-name> -- curl http://prometheus:9090/api/v1/query?query=up
```

**Solutions:**

1. **Verify toolsets are enabled:**
```yaml
toolsets:
  - name: "kubernetes"
    enabled: true
  - name: "prometheus"
    enabled: true
    config:
      url: "http://prometheus:9090"
```

2. **Check data source configuration:**
```bash
# Test Prometheus connectivity
curl "http://prometheus:9090/api/v1/query?query=up"

# Verify Kubernetes permissions
kubectl auth can-i get pods
```

### Incorrect Analysis

**Problem:** HolmesGPT provides inaccurate or irrelevant analysis.

**Solutions:**

1. **Improve question specificity:**
```bash
# Instead of: "what's wrong?"
# Try: "why is the payment-service pod restarting in the production namespace?"
```

2. **Provide context:**
```bash
# Include relevant time frame
holmes ask "what errors occurred in the last 30 minutes?"

# Reference specific resources
holmes ask "analyze the nginx-deployment in the web namespace"
```

3. **Check AI model configuration:**
```yaml
config:
  model: "gpt-4"  # Use more capable model
  temperature: 0.1  # More focused responses
```

## Monitoring and Observability

### Missing Metrics

**Problem:** Prometheus metrics not appearing.

**Solution:**
```bash
# Verify metrics endpoint
kubectl port-forward svc/holmesgpt 9090:9090
curl http://localhost:9090/metrics

# Check ServiceMonitor
kubectl get servicemonitor holmesgpt-metrics

# Verify Prometheus is scraping
kubectl port-forward svc/prometheus 9090:9090
# Open http://localhost:9090/targets
```

### Log Issues

**Problem:** Missing or incomplete logs.

**Solution:**
```bash
# Increase log level
helm upgrade holmesgpt holmesgpt/holmes --set config.logLevel=DEBUG

# Check log format
kubectl logs -l app=holmesgpt --tail=100

# Verify log rotation
kubectl describe pod <pod-name> | grep -A5 "Mounts"
```

## Resource Cleanup

### Removing Failed Installation

```bash
# List Helm releases
helm list

# Uninstall release
helm uninstall holmesgpt

# Clean up remaining resources
kubectl delete clusterrole holmesgpt-reader
kubectl delete clusterrolebinding holmesgpt-reader
kubectl delete secret holmes-secrets
```

### Reset Configuration

```bash
# Reset to default values
helm upgrade holmesgpt holmesgpt/holmes --reset-values

# Or start fresh
helm uninstall holmesgpt
helm install holmesgpt holmesgpt/holmes
```

## Getting Help

### Collecting Diagnostic Information

```bash
# Create support bundle
kubectl get all -l app=holmesgpt -o yaml > holmesgpt-resources.yaml
kubectl describe pods -l app=holmesgpt > holmesgpt-describe.txt
kubectl logs -l app=holmesgpt --previous > holmesgpt-logs.txt

# Helm information
helm status holmesgpt > helm-status.txt
helm get values holmesgpt > helm-values.yaml
```

### Enable Debug Mode

```yaml
# values.yaml
config:
  logLevel: "DEBUG"
  debug: true

env:
  - name: HOLMES_DEBUG
    value: "true"
```

### Community Support

1. **Slack Community**: [robustacommunity.slack.com](https://robustacommunity.slack.com){:target="_blank"}
2. **GitHub Issues**: [github.com/robusta-dev/holmesgpt/issues](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}
3. **Documentation**: [robusta-dev.github.io/holmesgpt](https://robusta-dev.github.io/holmesgpt/){:target="_blank"}

When reporting issues, please include:
- HolmesGPT version
- Kubernetes version
- Helm chart version
- Error messages and logs
- Configuration (with sensitive data removed)

## FAQ

### Q: HolmesGPT is not finding any issues despite obvious problems

**A:** Check that:
1. RBAC permissions allow access to relevant namespaces
2. Toolsets are properly configured and enabled
3. Data sources are accessible from the HolmesGPT pod
4. The question is specific enough for the AI to understand

### Q: API costs are too high

**A:** Optimize by:
1. Reducing `maxTokens` in configuration
2. Using a more cost-effective model
3. Enabling caching to reduce duplicate requests
4. Setting rate limits to control usage

### Q: HolmesGPT keeps timing out

**A:** Increase timeouts:
```yaml
config:
  timeout: 60s
  aiProvider:
    timeout: 45s
```

### Q: Cannot install in restricted environments

**A:** For air-gapped installations:
1. Mirror the container images to your private registry
2. Configure image pull secrets
3. Use custom CA certificates if needed
4. Disable internet-dependent toolsets
