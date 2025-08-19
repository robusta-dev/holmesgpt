# Investigating Prometheus Alerts

HolmesGPT provides two ways to investigate Prometheus/AlertManager alerts:

1. **Interactive Viewer** - Real-time monitoring and AI enrichment in a terminal UI
2. **Command-line Investigation** - One-time investigation of specific alerts

![Single Alert Investigation](../assets/alertmanager-single-alert-investigation.gif)

## Prerequisites

- HolmesGPT CLI installed ([installation guide](../installation/cli-installation.md))
- An AI provider API key configured ([setup guide](../ai-providers/index.md))
- Access to your AlertManager instance (auto-discovery works in Kubernetes)

## Interactive Alert Viewer

The interactive viewer provides a real-time dashboard for monitoring and enriching alerts with AI insights.

### Quick Start

```bash
# Auto-discover AlertManager in your cluster - no configuration needed!
holmes alerts view

# View alerts from a specific AlertManager
holmes alerts view --alertmanager-url http://localhost:9093

# Enrich ALL alerts with AI on startup (may be expensive!)
# Without this flag, you can manually enrich individual alerts with 'e' key
holmes alerts view --enable-enrichment

# Add custom AI columns for analysis
holmes alerts view \
  --ai-column "root_cause=identify the technical root cause" \
  --ai-column "affected_team=which team owns this service"
```

### Features

The interactive viewer includes:

- **Real-time Updates** - Polls AlertManager every 30 seconds
- **Auto-discovery** - Automatically finds AlertManager instances in Kubernetes
- **Three-pane Layout**:
  - Alert list with status and AI enrichment
  - Inspector for detailed alert information
  - Console for enrichment logs
- **Vim-style Navigation** - Keyboard shortcuts for efficient browsing
- **AI Enrichment** - Two modes:

  - Manual: Press 'e' to enrich selected alert or 'E' for all alerts
  - Automatic: Use `--enable-enrichment` flag to enrich all alerts on startup

### Keyboard Shortcuts

**Navigation:**

- `j/k` - Move down/up in the current pane
- `g/G` - Go to top/bottom of current pane
- `PgUp/PgDn` - Page up/down
- `Tab` - Switch between panes
- `l` - Focus alert list
- `i` - Toggle inspector pane
- `o` - Toggle console output

**Actions:**

- `e` - Enrich selected alert with AI
- `E` - Enrich all alerts
- `r` - Refresh alerts
- `/` - Start search
- `Enter` - Apply search filter
- `Esc` - Cancel search/clear filter
- `?` - Show help
- `q` - Quit

## Command-line Tools

### List Alerts

Quickly list all current alerts in table or JSON format:

```bash
# List all alerts in a table
holmes alerts list

# List alerts from specific AlertManager
holmes alerts list --alertmanager-url http://localhost:9093

# Output as JSON for scripting
holmes alerts list --format json

# Filter by severity
holmes alerts list --severity critical

# Filter by specific label
holmes alerts list --label "namespace=production"
```

This command is useful for:

- Quick status checks in scripts
- Piping to other tools (`holmes alerts list --format json | jq`)
- Integration with monitoring dashboards
- CI/CD pipelines

### Investigate Alerts

For one-time investigation of specific alerts without the interactive UI, use the `investigate` command.

### Step 1: Access AlertManager

If AlertManager isn't publicly accessible, forward it to your local machine:

```bash
kubectl port-forward svc/<Your-Alertmanager-Service> 9093:9093
```

### Step 2: Create a Test Alert (Optional)

Deploy a crashing workload and create a test alert:

```bash
# Deploy broken pod
kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/crashpod/broken.yaml

# Send test alert to AlertManager
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "KubePodCrashLooping",
        "severity": "warning",
        "namespace": "default",
        "pod": "payment-processing-worker",
        "container": "worker",
        "job": "kubernetes-pods"
      },
      "annotations": {
        "description": "Pod default/payment-processing-worker is crash looping",
        "summary": "Pod is in CrashLoopBackOff state"
      },
      "generatorURL": "http://prometheus:9090/graph?g0.expr=increase%28kube_pod_container_status_restarts_total%5B1h%5D%29%20%3E%205",
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }
  ]'
```

### Step 3: Run Investigation

Investigate all alerts or specific ones:

```bash
# Investigate all active alerts
holmes investigate alertmanager --alertmanager-url http://localhost:9093

# Investigate specific alert by name
holmes investigate alertmanager \
  --alertmanager-url http://localhost:9093 \
  --alertmanager-alertname "KubePodCrashLooping"
```

![AlertManager Alert Investigation](../assets/alertmanager-all-alert-investigation.png)

## Filtering Alerts

The `holmes investigate alertmanager` command supports many flags. For example, to investigate only critical alerts or alerts in a specific namespace, you can use the `--alertmanager-label` flag:

```bash
# Critical alerts only
holmes investigate alertmanager \
  --alertmanager-url http://localhost:9093 \
  --alertmanager-label "severity=critical"

# Production namespace issues
holmes investigate alertmanager \
  --alertmanager-url http://localhost:9093 \
  --alertmanager-label "namespace=production"
```


## What's Next?
- **[Add new data sources](../data-sources/index.md)** - Connect HolmesGPT to your databases, APM tools, and custom APIs for deeper investigations.
- **[Set up remote MCP](../data-sources/remote-mcp-servers.md)** - Add data sources as remote Model Context Protocol (MCP) servers.
