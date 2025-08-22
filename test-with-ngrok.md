# Testing Alert Proxy with Ngrok and Real AlertManager

## Prerequisites
- Install ngrok: `brew install ngrok` or download from https://ngrok.com
- Slack workspace with ability to create incoming webhooks

## Step-by-Step Testing Guide

### 1. Create Slack Incoming Webhook
1. Go to https://api.slack.com/apps
2. Create a new app or use existing
3. Enable "Incoming Webhooks"
4. Add new webhook to workspace
5. Copy the webhook URL (starts with `https://hooks.slack.com/services/...`)

### 2. Start the Alert Proxy
```bash
# Export your Slack webhook
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Start the proxy
poetry run holmes proxy-alertmanager \
  --port 8080 \
  --slack-webhook-url $SLACK_WEBHOOK_URL \
  --model gpt-4o-mini \
  --enable-investigation \
  --enrichment-timeout 15
```

### 3. Expose Proxy with Ngrok
In another terminal:
```bash
# Expose the proxy to the internet
ngrok http 8080

# You'll see output like:
# Forwarding  https://abc123.ngrok.io -> http://localhost:8080
# Copy the HTTPS URL
```

### 4. Configure AlertManager to Use Proxy

Create a test receiver in AlertManager:

```bash
# First, get current AlertManager config
kubectl get secret alertmanager-robusta-kube-prometheus-st-alertmanager -n default -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d > alertmanager-config.yaml

# Edit the config to add webhook receiver
cat >> alertmanager-config.yaml << 'EOF'

# Add this to the receivers section:
  - name: holmes-proxy
    webhook_configs:
      - url: https://YOUR-NGROK-URL.ngrok.io/webhook
        send_resolved: true
        http_config:
          follow_redirects: true
EOF

# Apply the updated config (backup first!)
kubectl create secret generic alertmanager-robusta-kube-prometheus-st-alertmanager \
  --from-file=alertmanager.yaml=alertmanager-config.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

# Reload AlertManager
kubectl rollout restart statefulset alertmanager-robusta-kube-prometheus-st-alertmanager -n default
```

### 5. Generate Test Alerts

Option A: Create a test PrometheusRule:
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: holmes-test-alerts
  namespace: default
spec:
  groups:
  - name: holmes-test
    interval: 30s
    rules:
    - alert: TestHighMemoryUsage
      expr: up == 1
      for: 1m
      labels:
        severity: warning
        component: holmes-test
      annotations:
        summary: "Test alert for Holmes AI enrichment"
        description: "This is a test alert to demonstrate AI-powered alert enrichment. Memory usage is at {{ $value }}%"

    - alert: TestDatabaseDown
      expr: up{job="prometheus"} == 1
      for: 1m
      labels:
        severity: critical
        component: database
      annotations:
        summary: "Test database connectivity issue"
        description: "Unable to connect to PostgreSQL primary database"
```

Apply it:
```bash
kubectl apply -f test-alerts.yaml
```

Option B: Use Prometheus API to create test alerts:
```bash
# Port-forward to Prometheus
kubectl port-forward -n default svc/robusta-kube-prometheus-st-prometheus 9090:9090 &

# Trigger test alert via API
curl -X POST http://localhost:9090/api/v1/admin/tsdb/clean_tombstones
```

### 6. Verify Enrichment

Check multiple places:
1. **Slack Channel**: You should see enriched alerts with AI-generated insights
2. **Proxy Stats**: `curl http://localhost:8080/stats`
3. **Proxy Logs**: Check the terminal running the proxy
4. **AlertManager UI**:
   ```bash
   kubectl port-forward -n default svc/robusta-kube-prometheus-st-alertmanager 9093:9093
   # Visit http://localhost:9093
   ```

## Testing with Real Cluster Issues

### Simulate Real Problems

1. **Create a CrashLooping Pod**:
```bash
kubectl create deployment crashloop --image=busybox -- sh -c "exit 1"
# Wait for alert to fire (usually 5-10 minutes)
```

2. **Create High Memory Usage**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: memory-hog
spec:
  containers:
  - name: memory-hog
    image: polinux/stress
    resources:
      requests:
        memory: "100Mi"
      limits:
        memory: "200Mi"
    command: ["stress"]
    args: ["--vm", "1", "--vm-bytes", "250M", "--vm-hang", "1"]
```

3. **Create Disk Pressure**:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: disk-filler
spec:
  containers:
  - name: disk-filler
    image: busybox
    command: ["sh", "-c", "while true; do dd if=/dev/zero of=/tmp/bigfile bs=1M count=1024; sleep 10; done"]
```

## Example Test Flow

```bash
# Terminal 1: Start proxy
poetry run holmes proxy-alertmanager \
  --port 8080 \
  --slack-webhook-url $SLACK_WEBHOOK_URL \
  --model gpt-4o-mini \
  -vv

# Terminal 2: Expose with ngrok
ngrok http 8080

# Terminal 3: Send test alert directly
curl -X POST https://YOUR-NGROK-URL.ngrok.io/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "receiver": "holmes-test",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "PodCrashLooping",
        "namespace": "production",
        "pod": "api-server-abc123",
        "severity": "critical"
      },
      "annotations": {
        "description": "Pod has restarted 15 times in the last hour",
        "summary": "Pod is crash looping"
      },
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"
    }],
    "groupLabels": {"namespace": "production"},
    "commonLabels": {"severity": "critical"},
    "commonAnnotations": {},
    "externalURL": "http://alertmanager:9093",
    "version": "4"
  }'
```

## Debugging Tips

1. **Check Proxy Logs**: Add `-vv` for verbose output
2. **Test Webhook First**: Use https://webhook.site for testing
3. **Verify Network**: Ensure ngrok tunnel is active
4. **Check AlertManager Logs**:
   ```bash
   kubectl logs -n default alertmanager-robusta-kube-prometheus-st-alertmanager-0
   ```
5. **Test Direct Connectivity**:
   ```bash
   # Test proxy health
   curl http://localhost:8080/health

   # Test ngrok tunnel
   curl https://YOUR-NGROK-URL.ngrok.io/health
   ```

## Cleanup

```bash
# Remove test resources
kubectl delete deployment crashloop
kubectl delete pod memory-hog disk-filler
kubectl delete prometheusrule holmes-test-alerts

# Stop port-forwards
pkill -f "port-forward"

# Stop ngrok
pkill ngrok
```
