# CLI Commands Reference

Complete reference for all HolmesGPT CLI commands.

## Global Options

These options are available for most commands:

| Option | Description | Default |
|--------|-------------|---------|
| `--api-key` | API key for the LLM provider | From env or config |
| `--model` | Model to use (e.g., gpt-4o, claude-3-5-sonnet) | gpt-4o |
| `--config` | Path to config file | ~/.holmes/config.yaml |
| `-v, --verbose` | Verbose output (can be repeated: -vv, -vvv) | - |
| `--help` | Show help message | - |

## Commands

### `holmes ask`

Ask questions about your infrastructure and get AI-powered answers.

```bash
holmes ask "what pods are failing and why?"
```

**Options:**

| Option | Description |
|--------|-------------|
| `--prompt-file` | File containing the prompt |
| `-f, --file` | Include file contents in prompt |
| `-i, --interactive` | Enter interactive mode after initial question |
| `-n, --no-interactive` | Disable interactive mode |
| `--show-tool-output` | Show output from each tool |
| `--refresh-toolsets` | Refresh toolset status cache |
| `--system-prompt-additions` | Additional system prompt content |

**Examples:**

```bash
# Basic usage
holmes ask "why is my pod crashing?"

# Include file context
holmes ask "explain this error" -f error.log

# Non-interactive mode for scripting
holmes ask "list unhealthy pods" --no-interactive

# Use different model
holmes ask "analyze memory usage" --model claude-3-5-sonnet
```

### `holmes check`

Run health checks and optionally send alerts.

```bash
holmes check [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--checks-file` | Path to checks configuration | ~/.holmes/checks.yaml |
| `--mode` | Run mode: 'alert' or 'monitor' | alert |
| `--parallel` | Run checks in parallel for faster execution | false |
| `--name` | Run specific check by name | - |
| `--tags` | Filter checks by tags | - |
| `--output` | Output format: 'table' or 'json' | table |
| `--watch` | Run checks continuously | false |
| `--interval` | Interval for watch mode (seconds) | 60 |
| `--repeat` | Override repeat count | - |
| `--failure-threshold` | Override failure threshold | - |

**Examples:**

```bash
# Run all checks
holmes check

# Monitor mode (no alerts)
holmes check --mode monitor

# Run checks in parallel for faster execution
holmes check --parallel

# Filter by tags
holmes check --tags critical,database

# Watch mode
holmes check --watch --interval 300

# JSON output for automation
holmes check --output json
```

### `holmes investigate`

Investigate issues from various sources (AlertManager, Jira, PagerDuty, etc.).

#### `holmes investigate alertmanager`

Investigate Prometheus/AlertManager alerts.

```bash
holmes investigate alertmanager [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--alertmanager-url` | AlertManager URL |
| `--alertmanager-alertname` | Filter by alert name (regex) |
| `--alertmanager-label` | Filter by label (key=value) |
| `-n` | Limit number of alerts |

**Example:**

```bash
holmes investigate alertmanager \
  --alertmanager-url http://alertmanager:9093 \
  --alertmanager-alertname "HighMemory.*"
```

#### `holmes investigate jira`

Investigate Jira tickets.

```bash
holmes investigate jira [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--jira-url` | Jira instance URL |
| `--jira-username` | Jira username (email) |
| `--jira-api-key` | Jira API key |
| `--jira-query` | JQL query |
| `--update` | Update tickets with findings |

**Example:**

```bash
holmes investigate jira \
  --jira-url https://company.atlassian.net \
  --jira-query "project=OPS AND status=Open"
```

#### `holmes investigate pagerduty`

Investigate PagerDuty incidents.

```bash
holmes investigate pagerduty [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--pagerduty-api-key` | PagerDuty API key |
| `--pagerduty-user-email` | User email for updates |
| `--pagerduty-incident-key` | Specific incident key |
| `--update` | Update incidents with findings |

#### `holmes investigate github`

Investigate GitHub issues.

```bash
holmes investigate github [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--github-owner` | Repository owner |
| `--github-repository` | Repository name |
| `--github-pat` | Personal access token |
| `--github-query` | Search query |
| `--update` | Update issues with findings |

### `holmes toolset`

Manage toolsets configuration and status.

#### `holmes toolset list`

List all available toolsets and their status.

```bash
holmes toolset list
```

**Output:**
```
✅ kubernetes/core - Kubernetes cluster operations
✅ prometheus/metrics - Query Prometheus metrics
❌ grafana/loki - Missing configuration
```

#### `holmes toolset refresh`

Refresh toolset status cache.

```bash
holmes toolset refresh
```

### `holmes version`

Display HolmesGPT version.

```bash
holmes version
```

## Configuration

### Config File

Default location: `~/.holmes/config.yaml`

```yaml
# AI Provider
model: gpt-4o
api_key: ${OPENAI_API_KEY}

# Toolset Configuration
custom_toolsets:
  - /path/to/custom/toolset.yaml

# Alert Destinations
slack_token: ${SLACK_TOKEN}
slack_channel: "#alerts"

# Source Integrations
alertmanager_url: http://alertmanager:9093
prometheus_url: http://prometheus:9090
```

### Environment Variables

Common environment variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `AZURE_API_KEY` | Azure OpenAI API key |
| `HOLMES_POST_PROCESSING_PROMPT` | Post-processing prompt |
| `HOLMES_JSON_OUTPUT_FILE` | JSON output file path |

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | General error or check failures |
| 2 | Invalid arguments |
| 130 | Interrupted (Ctrl+C) |

## Piping and Scripting

HolmesGPT supports Unix pipes and scripting:

```bash
# Pipe input to holmes
kubectl get pods | holmes ask "which pods are unhealthy?"

# Use in scripts with exit codes
if holmes check --tags critical; then
  echo "All critical checks passed"
else
  echo "Critical checks failed"
  exit 1
fi

# Parse JSON output
holmes check --output json | jq '.[] | select(.status == "FAIL")'

# Chain commands
holmes ask "list failing pods" --no-interactive | grep Error
```

## Interactive Mode

When using `holmes ask` without `--no-interactive`, you enter an interactive session with additional commands:

- `/help` - Show available slash commands
- `/clear` - Clear conversation history
- `/tools` - Show toolset status
- `/exit` - Exit interactive mode

See [Slash Commands](./slash-commands.md) for complete reference.

## Common Workflows

### Daily Health Check

```bash
#!/bin/bash
# Run critical checks every morning
holmes check --tags critical --mode alert
```

### Incident Investigation

```bash
# 1. Check current alerts
holmes investigate alertmanager -n 5

# 2. Ask about specific issue
holmes ask "why is the payment service failing?"

# 3. Run health checks
holmes check --tags payment-service
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Run Holmes Health Checks
  run: |
    holmes check --checks-file .holmes/checks.yaml --output json > results.json
    if [ $? -ne 0 ]; then
      echo "Health checks failed"
      cat results.json | jq '.[] | select(.status == "FAIL")'
      exit 1
    fi
```

## Troubleshooting

### No output or hangs

Check verbose mode:
```bash
holmes ask "test" -vvv
```

### Authentication errors

Verify API keys:
```bash
echo $OPENAI_API_KEY
holmes ask "test" --api-key "your-key"
```

### Toolset issues

Refresh toolset cache:
```bash
holmes toolset refresh
holmes toolset list
```

See [Troubleshooting Guide](./troubleshooting.md) for more details.
