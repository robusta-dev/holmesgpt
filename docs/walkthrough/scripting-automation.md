# Scripting and Automation

HolmesGPT supports non-interactive usage for scripting and automation, making it easy to integrate into monitoring systems, health checks, and automated workflows.

## Non-Interactive CLI Usage

While interactive mode is powerful, HolmesGPT also supports non-interactive usage for scripting and automation:

### Basic One-Shot Questions

```bash
holmes ask "what pods are failing in the default namespace?" --no-interactive
```

### Piping Input

```bash
# Pipe command output directly to Holmes
kubectl get events | holmes ask "what warnings should I worry about?"

# Pipe without a question (Holmes will analyze the output)
kubectl logs my-pod | holmes ask

# Pipe log files
cat /var/log/app.log | holmes ask "find errors in these logs"
```

### Including Files

```bash
# Include one or more files with your question
holmes ask "analyze these configurations" -f config.yaml -f deployment.yaml

# Combine piped input with files
kubectl get pod my-pod -o yaml | holmes ask "why won't this pod start?" -f events.log
```

## Scripting Examples

### Health Check Script

```bash
#!/bin/bash
# Health check script
holmes ask "check for any critical issues in the cluster" --no-interactive
```

### Automated Investigation

```bash
# Automated investigation
if kubectl get pods | grep -q "CrashLoopBackOff"; then
    kubectl get pods | holmes ask "investigate the crashing pods" -n
fi
```

### Batch Analysis

```bash
# Batch analysis
for namespace in $(kubectl get ns -o name | cut -d/ -f2); do
    echo "Checking namespace: $namespace"
    holmes ask "check for issues in namespace $namespace" -n
done
```

### Scheduled Monitoring

```bash
#!/bin/bash
# Scheduled cluster health check (run via cron)

LOG_FILE="/var/log/holmes-health-check.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting cluster health check" >> $LOG_FILE

# Check for critical issues
ISSUES=$(holmes ask "check for any critical issues in the cluster" --no-interactive)

if [[ $? -ne 0 ]] || [[ "$ISSUES" == *"CRITICAL"* ]]; then
    echo "[$DATE] Critical issues found:" >> $LOG_FILE
    echo "$ISSUES" >> $LOG_FILE

    # Send alert (example with Slack webhook)
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🚨 Cluster Health Alert: $ISSUES\"}" \
        $SLACK_WEBHOOK_URL
fi

echo "[$DATE] Health check completed" >> $LOG_FILE
```

### Integration with Monitoring Tools

```bash
# Prometheus AlertManager webhook handler
#!/bin/bash

# Parse alert data from AlertManager
ALERT_DATA=$(cat)
ALERT_NAME=$(echo "$ALERT_DATA" | jq -r '.alerts[0].labels.alertname')

# Use HolmesGPT to investigate the alert
echo "$ALERT_DATA" | holmes ask \
    "Investigate this Prometheus alert: $ALERT_NAME. What could be causing this issue?" \
    --no-interactive \
    --destination slack \
    --slack-channel "#alerts"
```

## Best Practices

- **Use `--no-interactive` flag** for all scripted usage
- **Handle exit codes** to detect failures in automation
- **Combine with monitoring tools** for automated incident response
- **Pipe relevant context** to provide HolmesGPT with necessary information
- **Set appropriate timeouts** for long-running investigations
- **Log results** for audit trails and debugging
