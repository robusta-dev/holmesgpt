# Health Checks with Holmes

Monitor your infrastructure health and send alerts when checks fail using the `holmes check` command.

## Overview

The `holmes check` command allows you to:

- Define health checks as simple yes/no questions
- Run checks periodically with automatic retries
- Set failure thresholds for handling transient issues
- Send alerts to Slack (and other destinations) when checks fail
- Filter checks by tags for targeted monitoring
- Use structured output with clear pass/fail results and explanations

## Quick Start

1. Create a checks configuration file (`~/.holmes/checks.yaml`):

```yaml
version: 1
defaults:
  timeout: 30
  mode: "alert"
  repeat: 3
  repeat_delay: 5
  failure_threshold: 1

checks:
  - name: "Pod Health Check"
    description: "Check if all pods are running"
    tags: ["kubernetes", "critical"]
    query: "Are all pods in the default namespace running without errors?"

  - name: "Memory Usage"
    description: "Check memory consumption"
    tags: ["performance", "monitoring"]
    query: "Are any pods using more than 90% of their memory limits?"
    mode: "monitor"  # Only log, don't alert
```

2. Run the checks:

```bash
# Run all checks
holmes check

# Run in monitor mode (no alerts)
holmes check --mode monitor

# Filter by tags
holmes check --tags critical

# Run specific check
holmes check --name "Pod Health Check"
```

## Configuration Format

### Structure

The checks configuration file uses YAML format with the following structure:

```yaml
version: 1

# Default settings for all checks
defaults:
  timeout: 30              # Max seconds for each check
  mode: "alert"           # "alert" or "monitor"
  repeat: 3               # Number of attempts
  repeat_delay: 5         # Seconds between attempts
  failure_threshold: 1    # Max failures allowed

# Alert destinations
destinations:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#alerts"

# Check definitions
checks:
  - name: "Check Name"
    description: "What this check does"
    tags: ["tag1", "tag2"]
    query: "Question to ask the AI?"
    destinations: ["slack"]
    # Optional overrides:
    mode: "monitor"
    repeat: 5
    failure_threshold: 2
    timeout: 60
```

### Check Fields

| Field | Required | Description | Default |
|-------|----------|-------------|---------|
| `name` | Yes | Unique name for the check | - |
| `query` | Yes | Yes/no question for the AI to answer | - |
| `description` | No | Human-readable description | - |
| `tags` | No | List of tags for filtering | `[]` |
| `destinations` | No | Alert destinations when check fails | `[]` |
| `mode` | No | "alert" or "monitor" | From defaults |
| `repeat` | No | Number of attempts | From defaults |
| `repeat_delay` | No | Seconds between attempts | From defaults |
| `failure_threshold` | No | Max failures before overall fail | From defaults |
| `timeout` | No | Max seconds for check | From defaults |

### Semantics

#### Repeat and Failure Threshold

The `repeat` and `failure_threshold` settings work together to handle transient failures:

- `repeat: 5` with `failure_threshold: 2` means:
  - Run the check 5 times
  - If 0, 1, or 2 checks fail → Overall PASS ✅
  - If 3, 4, or 5 checks fail → Overall FAIL ❌

This provides tolerance for flaky checks while still catching real issues.

#### Modes

- **`alert` mode**: Sends notifications to configured destinations when checks fail
- **`monitor` mode**: Only logs results, no alerts sent

## CLI Usage

### Basic Commands

```bash
# Run with default config (~/.holmes/checks.yaml)
holmes check

# Use custom config file
holmes check --checks-file /path/to/checks.yaml

# Override mode
holmes check --mode monitor  # No alerts
holmes check --mode alert    # Send alerts (default)
```

### Filtering

```bash
# Run checks with specific tags
holmes check --tags critical
holmes check --tags kubernetes,database

# Run specific check by name
holmes check --name "Database Connection"
```

### Output Formats

```bash
# Table format (default)
holmes check --output table

# JSON format for scripting
holmes check --output json
```

### Continuous Monitoring

```bash
# Watch mode - run checks continuously
holmes check --watch --interval 60  # Run every 60 seconds
```

### Override Settings

```bash
# Override repeat count for all checks
holmes check --repeat 5

# Override failure threshold
holmes check --failure-threshold 2

# Verbose output (shows rationales)
holmes check -v
```

## Examples

### Basic Health Checks

```yaml
version: 1
checks:
  - name: "API Health"
    query: "Is the Kubernetes API responding?"
    tags: ["critical"]

  - name: "High CPU"
    query: "Is any node CPU usage above 80%?"
    tags: ["performance"]
```

### Database Monitoring

```yaml
version: 1
defaults:
  repeat: 5
  failure_threshold: 2  # Allow 2 failures out of 5

checks:
  - name: "PostgreSQL Connection"
    query: "Can you connect to PostgreSQL at db.example.com:5432?"
    tags: ["database", "critical"]
    destinations: ["slack"]

  - name: "Database Performance"
    query: "Are database query response times under 100ms?"
    tags: ["database", "performance"]
    mode: "monitor"
```

### Kubernetes Cluster Health

```yaml
version: 1
destinations:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#ops-alerts"

checks:
  - name: "Control Plane Health"
    query: "Are all Kubernetes control plane components healthy?"
    tags: ["kubernetes", "critical"]
    destinations: ["slack"]

  - name: "Node Readiness"
    query: "Are all nodes in Ready state?"
    tags: ["kubernetes", "nodes"]

  - name: "PVC Usage"
    query: "Are any PersistentVolumeClaims above 85% capacity?"
    tags: ["kubernetes", "storage"]

  - name: "Pod Restarts"
    query: "Have any pods restarted more than 5 times in the last hour?"
    tags: ["kubernetes", "stability"]
```

### Security Checks

```yaml
version: 1
checks:
  - name: "Certificate Expiry"
    query: "Will any TLS certificates expire within 30 days?"
    tags: ["security", "certificates"]
    repeat: 1  # Check once daily

  - name: "Exposed Services"
    query: "Are any services exposed to the internet without authentication?"
    tags: ["security", "critical"]

  - name: "Security Policies"
    query: "Are all pods running with appropriate security contexts?"
    tags: ["security", "compliance"]
```

## Structured Output

Holmes uses structured JSON output to ensure reliable pass/fail determination. Each check returns:

```json
{
  "passed": true,
  "rationale": "All pods are running successfully with no errors detected"
}
```

This eliminates ambiguity and provides clear explanations for each result.

## Alert Integration

### Slack

Configure Slack alerts in your checks file:

```yaml
destinations:
  slack:
    webhook_url: ${SLACK_WEBHOOK_URL}
    channel: "#alerts"

checks:
  - name: "Critical Check"
    query: "Is the production database accessible?"
    destinations: ["slack"]
```

Set the webhook URL via environment variable:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
holmes check
```

### PagerDuty

Configure PagerDuty alerts using the Events API v2:

```yaml
destinations:
  pagerduty:
    integration_key: ${PAGERDUTY_INTEGRATION_KEY}

checks:
  - name: "Critical Service Check"
    query: "Is the payment service responding?"
    destinations: ["pagerduty"]
    tags: ["critical"]
```

Set the integration key via environment variable:

```bash
export PAGERDUTY_INTEGRATION_KEY="your-integration-key"
holmes check
```

PagerDuty incidents will be created with:
- Automatic deduplication based on check name
- Severity determined by tags (critical → critical, etc.)
- Full check details in custom fields

### Future Integrations

Support for additional destinations is planned:
- Email
- Webhooks
- OpsGenie

## Best Practices

### Writing Good Check Queries

✅ **Good queries are specific and measurable:**
- "Are all pods in the production namespace running?"
- "Is CPU usage on any node above 80%?"
- "Can you connect to PostgreSQL at db.prod:5432?"

❌ **Avoid vague or subjective queries:**
- "Is the system healthy?"
- "Are things working well?"
- "Check the infrastructure"

### Setting Failure Thresholds

Choose thresholds based on the check's reliability:

- **Stable checks**: Use `failure_threshold: 0` (no tolerance)
- **Network checks**: Use `failure_threshold: 1` or `2` for transient issues
- **External services**: Higher thresholds for third-party dependencies

### Organizing with Tags

Use consistent tagging for easier management:

```yaml
tags: ["critical", "database"]        # Severity + component
tags: ["monitoring", "prometheus"]     # Purpose + tool
tags: ["production", "frontend"]       # Environment + service
```

### Performance Considerations

- Set appropriate timeouts for long-running checks
- Use `repeat_delay` to avoid overwhelming systems
- Consider using `--watch` mode instead of cron for continuous monitoring
- Filter checks with tags to run subsets when needed

## Troubleshooting

### Checks Always Fail

1. Run with verbose mode to see rationales:
   ```bash
   holmes check -v
   ```

2. Verify the AI can access required tools:
   ```bash
   holmes ask "Can you list Kubernetes namespaces?"
   ```

3. Check that queries are properly phrased as yes/no questions

### No Alerts Sent

1. Verify mode is set to "alert":
   ```bash
   holmes check --mode alert
   ```

2. Check destination configuration:
   ```bash
   export SLACK_WEBHOOK_URL="your-webhook-url"
   ```

3. Ensure checks have `destinations` configured

### Performance Issues

1. Reduce repeat count for faster feedback:
   ```bash
   holmes check --repeat 1
   ```

2. Increase timeout for slow checks:
   ```yaml
   timeout: 60  # seconds
   ```

3. Use tags to run fewer checks:
   ```bash
   holmes check --tags critical
   ```

## Integration with CI/CD

Use exit codes for automation:

```bash
#!/bin/bash
holmes check --checks-file production-checks.yaml

if [ $? -eq 0 ]; then
  echo "All checks passed"
else
  echo "Some checks failed"
  exit 1
fi
```

JSON output for parsing:

```bash
holmes check --output json | jq '.[] | select(.status == "FAIL")'
```
