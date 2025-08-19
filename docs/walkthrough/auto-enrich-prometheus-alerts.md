# Auto-Enrich Prometheus Alerts

Turn cryptic alerts into actionable insights with AI enrichment.

## Before vs After

### Standard AlertManager Alert
```
🔴 HighMemoryUsage
pod=api-server-abc123
namespace=production
Memory usage is above 90% for pod api-server-abc123
```

### With HolmesGPT Enrichment
```
🔴 HighMemoryUsage
pod=api-server-abc123
namespace=production
Memory usage is above 90% for pod api-server-abc123

📊 AI Analysis:
Impact: ~1,200 users experiencing 2.3s slower checkout page loads
Root Cause: Memory leak from unclosed database connections after deploy at 14:32
Action: Restart pod api-server-abc123 or scale deployment to 5 replicas
Related: Database connection pool exhausted (see prometheus alert #4521)
```

## Quick Start

### 1. Start the Proxy (30 seconds)

```bash
# Basic enrichment
holmes alertmanager-proxy serve --port 8080

# With Slack notifications
holmes alertmanager-proxy serve --port 8080 --slack-webhook $SLACK_WEBHOOK
```

### 2. Configure AlertManager (1 minute)

```yaml
# alertmanager.yaml
receivers:
  - name: holmes-proxy
    webhook_configs:
      - url: http://holmes-proxy:8080/webhook

route:
  receiver: holmes-proxy
```

### 3. Done!

Every alert now includes:
- **Business Impact** - "Affecting 1,200 checkout users"
- **Root Cause** - "Memory leak from unclosed DB connections"
- **Suggested Fix** - "Restart pod or scale replicas"
- **Related Issues** - Links to correlated alerts

## Real Examples

### Example: OOM Kill Alert

**Original Alert:**
```yaml
alertname: KubePodCrashLooping
pod: payment-processor-5d4
```

**AI-Enriched Version:**
```yaml
summary: "Payment processor crashing due to memory limits"
business_impact: "~450 payments/hour failing, $12K revenue risk"
root_cause: "Pod requesting 512Mi but needs 1.2Gi for current load"
action: "Update deployment: memory request to 1.5Gi"
evidence: "10x traffic spike at 14:15, memory grew from 400Mi to 1.3Gi"
```

### Example: Database Alert

**Original Alert:**
```yaml
alertname: PostgresConnectionPoolExhausted
instance: postgres-primary
```

**AI-Enriched Version:**
```yaml
summary: "Database rejecting new connections, affecting 3 services"
business_impact: "Login and checkout completely down"
root_cause: "Leaked connections from api-server pods after deploy"
action: "1) Kill idle connections 2) Restart api-server pods"
affected_services: ["api-server", "checkout", "auth-service"]
```

## Custom AI Fields

Add organization-specific insights:

```bash
# Business-focused fields
holmes alertmanager-proxy serve \
  --ai-column "affected_team=Which team owns this?" \
  --ai-column "customer_impact=How many users affected?" \
  --ai-column "revenue_risk=Revenue impact per hour?"

# Technical analysis
holmes alertmanager-proxy serve \
  --ai-column "root_cause=Find the technical root cause" \
  --ai-column "runbook=Step-by-step fix instructions" \
  --ai-column "prevent=How to prevent this in future?"
```

## Deployment

### Kubernetes (Production)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: holmes-proxy
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: proxy
        image: ghcr.io/robusta-dev/holmesgpt:latest
        command: ["holmes", "alertmanager-proxy", "serve"]
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: holmes
              key: api-key
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: holmes
              key: slack-webhook
---
apiVersion: v1
kind: Service
metadata:
  name: holmes-proxy
spec:
  ports:
  - port: 8080
```

### Docker (Testing)

```bash
docker run -d \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e SLACK_WEBHOOK_URL=$SLACK_WEBHOOK \
  -p 8080:8080 \
  ghcr.io/robusta-dev/holmesgpt \
  holmes alertmanager-proxy serve
```

## Advanced Features

### Severity Filtering

```bash
# Only enrich critical alerts
holmes alertmanager-proxy serve --severity critical,warning
```

## Monitoring

```bash
# Check proxy health
curl http://holmes-proxy:8080/health

# View statistics
curl http://holmes-proxy:8080/stats
```

```json
{
  "alerts_processed": 1523,
  "enriched": 1511,
  "cache_hits": 512,
  "avg_enrichment_time": "1.2s"
}
```

## Troubleshooting

**Not receiving alerts?**
```bash
# Check connectivity
curl -X POST http://holmes-proxy:8080/webhook -d '{}'

# Enable debug logs
holmes alertmanager-proxy serve -vv
```

**Enrichment failing?**
```bash
# Test API key
export OPENAI_API_KEY=sk-...
holmes ask "test"

# Check proxy logs
kubectl logs -f deployment/holmes-proxy
```

## FAQ

**Q: Does it work with PagerDuty/OpsGenie?**
A: The proxy currently supports forwarding to Slack and AlertManager. For PagerDuty/OpsGenie, you can forward enriched alerts to AlertManager which then routes to these services.

**Q: Can I use my own LLM?**
A: Yes, supports OpenAI, Anthropic, Azure, Bedrock, and local models via the --model flag.
