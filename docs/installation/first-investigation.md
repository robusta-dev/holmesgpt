# First Investigation

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

## Step 5: Try More Scenarios

Create different types of issues to see Holmes in action:

```bash
# Image Pull Error
kubectl run bad-image --image=nonexistent:latest
holmes ask "why is the bad-image pod failing?"

# Resource Limits
kubectl run memory-hog --image=nginx --requests='memory=100Gi'
holmes ask "what's wrong with the memory-hog pod?"

# Application Crash
kubectl run crash-pod --image=busybox --command -- sh -c 'exit 1'
holmes ask "why does crash-pod keep restarting?"
```

## Step 6: Advanced Usage

### Using Context Files

Provide additional context to Holmes:

```bash
# Save pod logs to a file
kubectl logs user-profile-import > pod-logs.txt

# Ask Holmes to analyze with context
holmes ask "analyze this pod failure" --file pod-logs.txt
```

### Cluster-wide Questions

```bash
holmes ask "what nodes are having problems?"
holmes ask "show me all unhealthy workloads"
holmes ask "are there any networking problems?"
```

## Tips for Better Results

### Be Specific
- ❌ "something is broken"
- ✅ "why is the checkout service returning 500 errors?"

### Use Interactive Mode
```bash
holmes ask "what's wrong with my cluster?" --interactive
```

## Clean Up

Remove the test resources:

```bash
kubectl delete pod user-profile-import bad-image memory-hog crash-pod
```

## Next Steps

🎉 **Congratulations!** You've successfully run your first HolmesGPT investigations.

- **[Configure Data Sources](../data-sources/)** - Add monitoring tools like Prometheus, Grafana
- **[Python SDK](python-installation.md)** - Embed Holmes in your applications
- **[Helm Chart](kubernetes-installation.md)** - Deploy as a service

## Need Help?

- Join our [Slack community](https://robustacommunity.slack.com)
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
