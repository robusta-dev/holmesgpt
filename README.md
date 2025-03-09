<div align="center">
  <h1 align="center">Solve alerts faster with an AI Agent</h1>
  <p align="center">
    <a href="#how-it-works"><strong>How it Works</strong></a> |
    <a href="#quick-start-installating-holmesgpt"><strong>Quick Start</strong></a> |
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

<img width="600" alt="example-holmesgpt-analysis" src="https://github.com/user-attachments/assets/d03df693-9eff-4d61-8947-2b101f648c3e" />

### How it Works

HolmesGPT connects AI models with live observability data and organizational knowledge. It uses an **agentic loop** to analyze data from multiple sources and identify possible root causes.

<img width="3114" alt="holmesgpt-architecture-diagram" src="https://github.com/user-attachments/assets/f659707e-1958-4add-9238-8565a5e3713a" />

### 📈 Data Sources

The following data sources ("toolsets") are built-in. [Add your own](#customizing-holmesgpt).

| Data Source    | Status         | Description                                                  |
|----------------|----------------|--------------------------------------------------------------|
| Kubernetes     | ✅             | Pod logs, K8s events, and resource status (kubectl describe) |
| Grafana        | ✅             | [Logs (Loki)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafana.html) and [traces (Tempo)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafana.html#tempo) |
| Helm           | ✅             | Release status, chart metadata, and values                   |
| ArgoCD         | ✅             | Application sync status                                      |
| AWS RDS        | ✅             | Logs and events                                              |
| Prometheus     | ✅             | Currently supports investigating alerts; coming soon: automatically write PromQL and show related graphs |
| Internet       | ✅             | Public runbooks                                              |
| Confluence     | ✅             | Private runbooks and documentation                           |
| OpenSearch     | 🟡 Beta        | Query logs and investigate issues with OpenSearch itself (using self-health diagnostics) |
| NewRelic       | 🟡 Beta        | Investigate alerts, query tracing data                       |
| Coralogix      | 🟡 Beta        | Logs                                                         |
| GitHub         | 🟡 Beta        | Remediate alerts by opening pull requests with fixes         |

[How to configure datasources with Robusta SaaS](https://docs.robusta.dev/master/configuration/holmesgpt/builtin_toolsets.html) (docs for CLI coming soon)

[Request access to beta features](mailto:beta@robusta.dev)

### 🔐 Data Privacy

By design, HolmesGPT has **read-only access** and respects RBAC permissions. It is safe to run in production environments.

We do **not** train HolmesGPT on your data. Data sent to Robusta SaaS is private to your account.

For extra privacy, [bring an API key](docs/api-keys.md) for your own AI model.

### 🚀 Bi-Directional Integrations With Your Tools

Robusta can investigate alerts - or just answer questions - from the following sources:

| Integration             | Status    | Notes |
|-------------------------|-----------|-------|
| Slack                   | 🟡 Beta   | [Demo.](https://www.loom.com/share/afcd81444b1a4adfaa0bbe01c37a4847) Tag HolmesGPT bot in any Slack message |
| Prometheus/AlertManager | ✅        | Robusta SaaS or HolmesGPT CLI |
| PagerDuty               | ✅        | HolmesGPT CLI only |
| OpsGenie                | ✅        | HolmesGPT CLI only |
| Jira                    | ✅        | HolmesGPT CLI only |

### See it in Action

<a href="https://www.loom.com/share/4c55f395dbd64ef3b69670eccf961124" target="_blank">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/4c55f395dbd64ef3b69670eccf961124-db2004995e8d621c-full-play.gif">
</a>

## Quick Start - Installing HolmesGPT

HolmesGPT can be used in three ways:

1. [Use Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) (**recommended**) for the full HolmesGPT experience (Kubernetes required)
2. [Desktop CLI](docs/installation.md) or [K9s plugin](docs/k9s.md) - no Kubernetes required, supports one-off investigations
3. [Python library](docs/python.md) - for advanced use cases

### Using HolmesGPT

- In the Robusta SaaS: Go to [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and use Holmes from your browser
- With HolmesGPT CLI: [setup an LLM API key](docs/api-keys.md) and ask Holmes a question 👇

```bash
holmes ask "what pods are unhealthy and why?"
```

Also supported:

<details>
<summary>HolmesGPT CLI: investigate Prometheus alerts</summary>

Pull alerts from AlertManager and investigate them with HolmesGPT:

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093
# if on Mac OS and using the Holmes Docker image👇
#  holmes investigate alertmanager --alertmanager-url http://docker.for.mac.localhost:9093
```

<b>To investigate alerts in your browser, sign up for a free trial of [Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section). </b>


<b>Optional:</b> port-forward to AlertManager before running the command mentioned above (if running Prometheus inside Kubernetes)

```bash
kubectl port-forward alertmanager-robusta-kube-prometheus-st-alertmanager-0 9093:9093 &
```
</details>

<details>
<summary>HolmesGPT CLI: investigate PagerDuty and OpsGenie alerts</summary>

```bash
holmes investigate opsgenie --opsgenie-api-key <OPSGENIE_API_KEY>
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY>
# to write the analysis back to the incident as a comment
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY> --update
```

For more details, run `holmes investigate <source> --help`
</details>

## Customizing HolmesGPT

HolmesGPT can investigate many issues out of the box, with no customization or training. Optionally, you can extend Holmes to improve results:

**Custom Data Sources**: Add data sources (toolsets) to improve investigations
   - If using Robusta SaaS: See [Robusta's docs](https://docs.robusta.dev/master/configuration/holmesgpt/custom_toolsets.html)
   - If using the CLI: Use `-t` flag with [custom toolset files](./examples/custom_toolset.yaml) or add to `~/.holmes/config.yaml`

**Custom Runbooks**: Give HolmesGPT instructions for known alerts:
   - If using Robusta SaaS: Use the Robusta UI to add runbooks
   - If using the CLI: Use `-r` flag with [custom runbook files](./examples/custom_runbooks.yaml) or add to `~/.holmes/config.yaml`

You can save common settings and API Keys in a config file to avoid passing them from the CLI each time:

<details>
<summary>Reading settings from a config file</summary>

You can save common settings and API keys in config file for re-use. Place the config file in <code>~/.holmes/config.yaml`</code> or pass it using the <code> --config</code>

You can view an example config file with all available settings [here](config.example.yaml).
</details>

## License
Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/holmesgpt/blob/master/LICENSE.txt) for more information.
<!-- Change License -->

## Support

If you have any questions, feel free to message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)

## How to Contribute

Install HolmesGPT from source with Poetry. See [Installation](docs/installation.md) for details.

For help, contact us on [Slack](https://bit.ly/robusta-slack)
