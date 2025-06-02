# Run Your First Investigation

This guide walks you through running your first HolmesGPT investigation, assuming you've installed the CLI.

## Prerequisites

Before starting, ensure you have:

- ✅ **HolmesGPT CLI installed** - See [CLI Installation Guide](cli-installation.md)
- ✅ **AI provider API key configured** - See [API Keys Setup](../api-keys.md)
- ✅ **kubectl access to a Kubernetes cluster** - Any cluster will work

## Step 1: Verify Your Setup

First, let's make sure everything is working:

```bash
# Check Holmes is installed
holmes --help

# Check kubectl access
kubectl cluster-info

# Verify your API key is set (choose one)
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $GOOGLE_API_KEY
```

## Step 2: Create a Test Scenario

Let's create a problematic pod that Holmes can investigate:

```bash
# Create a pod with a common issue (wrong node selector)
kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
```

This creates a pod that will remain in "Pending" state due to an invalid node selector.

## Step 3: Your First Investigation

Now let's ask Holmes to investigate:

```bash
holmes ask "what is wrong with the user-profile-import pod?"
```

**Expected output:**
```
🔍 Investigating: what is wrong with the user-profile-import pod?

📋 Investigation Summary:
The user-profile-import pod is in Pending state due to an invalid node selector.
The pod specifies nodeSelector: gpu-node=true, but no nodes in the cluster
have this label.

🔧 Recommended Actions:
1. Remove the nodeSelector constraint, or
2. Add the required label to a node: kubectl label node <node-name> gpu-node=true

📊 Resource Details:
- Pod Status: Pending
- Namespace: default
- Node Selector: gpu-node=true
- Available Nodes: 3 (none matching selector)
```

## Step 4: Try Interactive Mode

For follow-up questions, use interactive mode:

```bash
holmes ask "what pods are failing?" --interactive
```

This starts an interactive session where you can ask follow-up questions:

```
🔍 Investigating: what pods are failing?

📋 Investigation found 1 failing pod:
- user-profile-import (Pending): Invalid node selector

💬 Ask a follow-up question (or 'quit' to exit):
> how do I fix the node selector issue?

🔧 To fix the node selector issue, you have two options:

1. Remove the nodeSelector (recommended):
   kubectl patch pod user-profile-import -p '{"spec":{"nodeSelector":null}}'

2. Label a node to match:
   kubectl label node worker-1 gpu-node=true

> quit
```

## Step 5: Investigate Different Scenarios

Let's create and investigate different types of issues:

### Image Pull Error

```bash
# Create pod with non-existent image
kubectl run bad-image --image=nonexistent:latest

# Investigate
holmes ask "why is the bad-image pod failing?"
```

### Resource Limits

```bash
# Create pod requesting too much memory
kubectl run memory-hog --image=nginx --requests='memory=100Gi'

# Investigate
holmes ask "what's wrong with the memory-hog pod?"
```

### Application Crash

```bash
# Create a crashing pod
kubectl run crash-pod --image=busybox --command -- sh -c 'exit 1'

# Investigate
holmes ask "why does crash-pod keep restarting?"
```

## Step 6: Investigate Real Alerts

If you have Prometheus AlertManager, investigate real alerts:

### From AlertManager

```bash
# Port-forward to AlertManager (if running in cluster)
kubectl port-forward -n monitoring svc/alertmanager 9093:9093 &

# Investigate current alerts
holmes investigate alertmanager --alertmanager-url http://localhost:9093
```

### From PagerDuty

```bash
# Investigate PagerDuty incidents
holmes investigate pagerduty --pagerduty-api-key YOUR_API_KEY

# Update incident with analysis
holmes investigate pagerduty --pagerduty-api-key YOUR_API_KEY --update
```

### From OpsGenie

```bash
# Investigate OpsGenie alerts
holmes investigate opsgenie --opsgenie-api-key YOUR_API_KEY
```

## Step 7: Advanced Questions

Try these more advanced investigation scenarios:

### Cluster-wide Issues

```bash
holmes ask "what nodes are having problems?"
holmes ask "show me all unhealthy workloads"
holmes ask "what's consuming the most resources?"
```

### Performance Issues

```bash
holmes ask "why is my application slow?"
holmes ask "what pods are being throttled?"
holmes ask "show me memory usage trends"
```

### Networking Issues

```bash
holmes ask "are there any networking problems?"
holmes ask "why can't pods reach the database?"
holmes ask "show me service connectivity issues"
```

## Step 8: Using Context Files

Provide additional context to Holmes:

```bash
# Save pod logs to a file
kubectl logs user-profile-import > pod-logs.txt

# Ask Holmes to analyze with context
holmes ask "analyze this pod failure" --file pod-logs.txt

# Multiple files
holmes ask "investigate this deployment" \
  --file deployment.yaml \
  --file logs.txt \
  --file metrics.json
```

## Tips for Better Investigations

### 1. Be Specific

❌ **Vague:** "something is broken"
✅ **Specific:** "why is the checkout service returning 500 errors?"

### 2. Include Context

❌ **No context:** "fix this"
✅ **With context:** "the payment pod is crashing since the last deployment"

### 3. Use Interactive Mode

For complex issues, start broad and narrow down:

```bash
holmes ask "what's wrong with my cluster?" --interactive
> which namespace has the most issues?
> what's wrong with the payment service?
> how do I fix the database connection errors?
```

### 4. Provide Timeframes

```bash
holmes ask "what problems started in the last hour?"
holmes ask "show me errors since yesterday"
```

## Common Patterns

### Deployment Issues

```bash
# After a deployment
holmes ask "are there any issues with the latest deployment?"
holmes ask "did the rollout succeed in the production namespace?"
```

### Resource Problems

```bash
# Resource monitoring
holmes ask "what pods are using too much memory?"
holmes ask "which nodes are overloaded?"
```

### Application Errors

```bash
# Application debugging
holmes ask "why are users getting timeout errors?"
holmes ask "what's causing the high error rate?"
```

## Clean Up

Remove the test resources:

```bash
kubectl delete pod user-profile-import
kubectl delete pod bad-image
kubectl delete pod memory-hog
kubectl delete pod crash-pod
```

## Next Steps

Now that you've run your first investigations:

- **[Configure Custom Toolsets](../configuration/)** - Add your monitoring tools
- **[Set Up Runbooks](../configuration/)** - Create organization-specific guidance
- **[Integrate with CI/CD](python-installation.md)** - Automate investigation in pipelines
- **[Deploy as a Service](kubernetes-installation.md)** - Use HTTP API for integrations

## Need Help?

- **Common issues**: Check our [troubleshooting guide](../configuration/)
- **Community support**: Join our [Slack community](https://robustacommunity.slack.com)
- **Bug reports**: Create an issue on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)

## What's Next?

🎉 **Congratulations!** You've successfully run your first HolmesGPT investigations.

Holmes gets more powerful as you:
- Connect more data sources (Prometheus, Grafana, etc.)
- Add custom runbooks for your specific infrastructure
- Integrate with your existing workflows and tools

Happy investigating! 🕵️
