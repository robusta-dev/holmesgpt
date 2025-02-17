<div align="center">
  <h1 align="center">Solve alerts faster with an AI Agent</h1>
  <p align="center">
    <a href="#ways-to-use-holmesgpt"><strong>Examples</strong></a> |
    <a href="#key-features"><strong>Key Features</strong></a> |
    <a href="#installation"><strong>Installation</strong></a> |
    <a href="https://www.youtube.com/watch?v=TfQfx65LsDQ"><strong>YouTube Demo</strong></a>
  </p>
</div>

Respond to alerts faster, using AI to automatically:

- Fetch logs, traces, and metrics
- Determine if issues are application or infrastructure related
- Find upstream root-causes

Using HolmesGPT, you can transform your existing alerts from this 👇

![Before HolmesGPT](https://github.com/user-attachments/assets/931ebd71-ccd2-4b7b-969d-a061a99cec2d)

To this 👇

<div align="center">
  <img src="https://github.com/user-attachments/assets/238d385c-70b5-4f41-a3cd-b7785f49d74c" alt="Prometheus alert with AI investigation" width="500px" />
</div>

### How it Works

HolmesGPT connects AI models with live observability data and knowledge bases, using an **agentic loop** to analyze data from multiple sources and identify possible root causes.

<img width="3114" alt="holmesgpt-architecture-diagram" src="https://github.com/user-attachments/assets/f659707e-1958-4add-9238-8565a5e3713a" />

### 📈 Data Sources

The following data sources ("toolsets")  are built-in:

| Data Source    | Status         | Description                                                  |
|----------------|----------------|--------------------------------------------------------------|
| Kubernetes     | ✅             | Pod logs, K8s events, and resource status (kubectl describe) |
| Grafana        | ✅             | [Loki (logs)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafana.html) and ✅ [Tempo (traces)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafana.html#tempo) |
| Helm           | ✅             | Release status, chart metadata, and values                   |
| ArgoCD         | ✅             | Application sync status                                      |
| AWS RDS        | ✅             | Logs and events                                              |
| Prometheus     | ✅             | Currently supports investigating alerts; coming soon: automatically write PromQL and show related graphs |
| Internet       | ✅             | Public runbooks                                              |
| Confluence     | ✅             | Private runbooks and documentation                           |
| OpenSearch     | 🟡 Beta        | Query logs and investigate issues with OpenSearch itself (using self-health diagnostics) |
| NewRelic       | 🟡 Beta        | Investigate alerts, query tracing data                       |
| Coralogi       | 🟡 Beta        | Logs                                                         |
| GitHub         | 🟡 Beta        | Remediate alerts by opening pull requests with fixes         |

If you use Robusta SaaS, refer [Robusta's documentation for builtin toolsets](https://docs.robusta.dev/master/configuration/holmesgpt/builtin_toolsets.html). (Docs for CLI users are coming soon!)

To request access to beta features, message beta@robusta.dev.

### 🔐 Data Privacy

By design, HolmesGPT has limited **read-only access** to your datasources and respects RBAC permissions.

Robusta **does not train HolmesGPT** on your data, and when using Robusta SaaS no data is shared between customers.

For extra privacy, you can [bring your own API key](docs/api-keys.md) (OpenAI, Azure, AWS Bedrock, etc) so data is only sent to an approved LLM in your cloud account.

### 🚀 Bi-Directional Integrations With Your Tools

Robusta can investigate alerts - or even just answer questions - from the following sources:

| Integration             | Status    | Notes |
|-------------------------|-----------|-------|
| Slack                   | 🟡 Beta   | Tag HolmesGPT bot in any Slack message to invoke it |
| Prometheus/AlertManager | ✅        | Can be used with Robusta SaaS or HolmesGPT cli |
| PagerDuty               | ✅        | HolmesGPT CLI only |
| OpsGenie                | ✅        | HolmesGPT CLI only | 
| Jira                    | ✅        | HolmesGPT CLI only | 

### See it in Action

<a href="https://www.loom.com/share/4c55f395dbd64ef3b69670eccf961124" target="_blank">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/4c55f395dbd64ef3b69670eccf961124-db2004995e8d621c-full-play.gif">
</a>

## Quick Start

HolmesGPT can be used in three ways:

1. [Install Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) (**recommended**) for the full HolmesGPT experience (Kubernetes required)
2. [Use HolmesGPT as a local CLI](docs/installation.md) or [K9s plugin](docs/k9s.md) - no Kubernetes required, can be used for one-off investigations
3. [Import HolmesGPT as a Python library](docs/python.md) - for advanced use cases

## Using HolmesGPT

If you installed Robusta + HolmesGPT, go to [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and use Holmes from your browser.

If you installed HolmesGPT as a CLI tool, you'll need to first [setup an API key](#getting-an-api-key). Then ask Holmes a question:

```bash
holmes ask "what pods are unhealthy and why?"
```

Also supported: 

<details>
<summary>Prometheus/AlertManager alerts</summary>

To do a one-off investigation with the cli, first port-forward to AlertManager (if necessary)

```bash
kubectl port-forward alertmanager-robusta-kube-prometheus-st-alertmanager-0 9093:9093 &
# if on Mac OS and using the Holmes Docker image👇
#  holmes investigate alertmanager --alertmanager-url http://docker.for.mac.localhost:9093
```

Then run HolmesGPT with the AlertManager URL:

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093
# if on Mac OS and using the Holmes Docker image👇
#  holmes investigate alertmanager --alertmanager-url http://docker.for.mac.localhost:9093
```

For the full experience, sign up for a free trial of [Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and investigate alerts from your browser.

</details>

<details>
<summary>PagerDuty and OpsGenie</summary>

```bash
holmes investigate opsgenie --opsgenie-api-key <OPSGENIE_API_KEY>
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY>
# to write the analysis back to the incident as a comment
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY> --update
```

For more details, run `holmes investigate <source> --help`
</details>

## Customizing HolmesGPT

HolmesGPT can investigate many issues out of the box, with no customization or training.

That said, we provide several extension points for teaching HolmesGPT to investigate your issues, according to your best practices. The two main extension points are:

<details>
<summary>Add Custom Tools</summary>

The more data you give HolmesGPT, the better it will perform. Tools are HolmesGPT's way of accessing live data from your observability tools.

When running HolmesGPT in-cluster, refer to [Robusta's online docs](https://docs.robusta.dev/master/configuration/holmesgpt/custom_toolsets.html) which list all available tools and how to configure them.

When running HolmesGPT as a cli, new tools are loaded using `-t` from [custom toolset files](./examples/custom_toolset.yaml) or by adding them to the `~/.holmes/config.yaml` with the setting `custom_toolsets: ["/path/to/toolset.yaml"]`.
</details>

<details>
<summary>Add Custom Runbooks</summary>

HolmesGPT can investigate by following runbooks written in plain English. Add your own runbooks to provided the LLM specific instructions.

New runbooks are loaded using `-r` from [custom runbook files](./examples/custom_runbooks.yaml) or by adding them to the `~/.holmes/config.yaml` with the `custom_runbooks: ["/path/to/runbook.yaml"]`.
</details>

You can save settings in a config file to avoid passing them to the CLI each time:

<details>
<summary>Reading settings from a config file</summary>

You can customize HolmesGPT's behaviour with command line flags, or you can save common settings in config file for re-use.

You can view an example config file with all available settings [here](config.example.yaml).

</details>

## License
Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/holmesgpt/blob/master/LICENSE.txt) for more information.
<!-- Change License -->

## Support

If you have any questions, feel free to message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)

## How to Contribute

To contribute to HolmesGPT, follow the <a href="#installation"><strong>Installation</strong></a> instructions for **running HolmesGPT from source using Poetry.**

Feel free to ask us for help on [Slack](https://bit.ly/robusta-slack)
