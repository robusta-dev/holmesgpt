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

### Key Features

🔍 **Automatic Data Correlation**

Holmes supports the following observability sources:

| Data Source | Description |
|-------------|-------------|
| Kubernetes | Pod logs, k8s events, resource status (kubectl describe) |
| Grafana Loki | Logs |
| Grafana Tempo | Traces |
| Helm | Read Helm charts and values |
| ArgoCD | Check sync status |
| AWS RDS | DB logs and metrics |
| Prometheus | Alerts and metrics (ability to render graphs coming soon) |
| OpenSearch | Self-diagnostics (ability to query logs coming soon) |

📚 **Learns Your Knowledge Bases**

Optional: if you have runbooks or documentation about your architecture, Holmes can use them to guide its investigations.

| Source | Description |
|--------|-------------|
| Internet | For public runbooks and documentation |
| Confluence | For private runbooks and documentation |

🔒 **Enterprise-Ready**
- Read-only data access - respects RBAC permissions
- [Bring your own API key](docs/api-keys.md) (OpenAI, Azure, AWS Bedrock, etc.)
- Privacy-focused design - can keep all data in your cloud account

🚀 **Bi-Directional Integrations With Your Tools**

| Integration | Description |
|-------------|-------------|
| Slack | Tag HolmesGPT bot in Slack messages and ask it to investigate (coming soon) |
| Prometheus/AlertManager | Investigate alerts |
| PagerDuty | Investigate incidents |
| OpsGenie | Investigate incidents |
| Jira | Investigate tickets |

HolmesGPT has a number of toolsets that give it access to many datasources. This enhances HolmesGPT's ability to get to the root cause of issues.

These toolsets are documented on [Robusta's documentation for builtin toolsets](https://docs.robusta.dev/master/configuration/holmesgpt/builtin_toolsets.html),
although this documentation applies to running Holmes in clusters and not with the CLI.

### See it in Action

<a href="https://www.loom.com/share/4c55f395dbd64ef3b69670eccf961124">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/4c55f395dbd64ef3b69670eccf961124-db2004995e8d621c-full-play.gif">
</a>

## Quick Start

HolmesGPT can be used in three ways:

1. [Install Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) (**recommended**) for the full HolmesGPT experience (Kubernetes required)
2. [Use HolmesGPT as a local CLI](docs/installation.md) or [K9s plugin](docs/k9s.md) - no Kubernetes required, can be used for one-off investigations
3. [Import HolmesGPT as a Python library](docs/python.md) - for advanced use cases

## Using HolmesGPT

If you installed Robusta + HolmesGFPT, go to [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and use Holmes from your browser.

If you installed HolmesGPT as a CLI tool, you'll need to first [setup an API key](#getting-an-api-key). Then ask Holmes a question:

```bash
holmes ask "what pods are unhealthy and why?"
```

The CLI also supports pulling alerts and investigating them from AlertManager, PagerDuty, OpsGenie, and more.  

<details>
<summary>Prometheus/AlertManager alerts</summary>
</details>

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
