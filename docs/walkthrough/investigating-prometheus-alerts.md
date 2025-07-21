# Investigating Prometheus Alerts

You can investigate Prometheus/AlertManager alerts using HolmesGPT by connecting it to your AlertManager instance. This allows you to run investigations on all active alerts or a specific alert and optionally send the results to a Slack channel.

## Prerequisites

- HolmesGPT CLI installed ([installation guide](../installation/cli-installation.md))
- An AI provider API key configured ([setup guide](../ai-providers/index.md))
- Access to your AlertManager instance

## Investigating a Prometheus Alert Using HolmesGPT


### Step 1: Create a Test Alert

Let's create a dummy alert in Prometheus for our investigation. Run the following command to create a`KubePodCrashLooping` alert:

```yaml
kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/crashpod/broken.yaml
```

### Step 2: Forward AlertManager

Next you need to forward the AlertManager service to your local machine so HolmesGPT can connect to it. Run the following command in your terminal:

```bash
kubectl port-forward svc/<your-alertmanager-service> 9093:9093
```

### Step 3: Investigate Alerts

Run the following command to investigate the alerts:

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093
```
![AlertManager Alert Investigation](../assets/alertmanager-all-alert-investigation.png)

By default, HolmesGPT will fetch all active alerts from AlertManager and analyze them. You can also specify a particular alert to investigate by using the `--alertmanager-alertname` flag.

In this case, to investigate the `KubePodCrashLooping` alert we deployed, run:

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093 --alertmanager-alertname "KubePodCrashLooping"
```

![Single Alert Investigation](../assets/alertmanager-single-alert-investigation.gif)



## Filtering Alerts

You can also filter alerts by labels. For example, to investigate only critical alerts or alerts in a specific namespace, you can use the `--alertmanager-label` flag:

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

Once you've seen HolmesGPT investigate a few alerts, you might want to:

- Set up [custom toolsets](../data-sources/custom-toolsets.md) for your specific monitoring stack
- Send results to Slack channels automatically
- Create custom investigation workflows for your most common alert types
