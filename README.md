<div align="center">
  <h1 align="center">Solve alerts faster with an AI Agent</h1>
  <p align="center">
    <a href="#how-it-works"><strong>How it Works</strong></a> |
    <a href="#installation-options"><strong>Installation</strong></a> |
    <a href="#supported-llm-providers"><strong>LLM Providers</strong></a> |
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
| [Kubernetes](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/kubernetes.html)     | ✅             | Pod logs, K8s events, and resource status (kubectl describe) |
| Grafana       | ✅             | [Logs (Loki)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanaloki.html) and [traces (Tempo)](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/grafanatempo.html) |
| [Helm](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/helm.html)           | ✅             | Release status, chart metadata, and values                   |
| [ArgoCD](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/argocd.html)         | ✅             | Application sync status                                      |
| [AWS RDS](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/aws.html)        | ✅             | Logs and events                                              |
| [Prometheus](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/prometheus.html)     | ✅             | Currently supports investigating alerts; coming soon: automatically write PromQL and show related graphs |
| [Internet](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/internet.html)       | ✅             | Public runbooks                                              |
| [Confluence](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/confluence.html)     | ✅             | Private runbooks and documentation                           |
| [OpenSearch](https://docs.robusta.dev/master/configuration/holmesgpt/toolsets/opensearch.html)     | 🟡 Beta        | Query logs and investigate issues with OpenSearch itself (using self-health diagnostics) |
| NewRelic      | 🟡 Beta        | Investigate alerts, query tracing data                       |
| Coralogix      | 🟡 Beta        | Logs                                                         |
| GitHub        | 🟡 Beta        | Remediate alerts by opening pull requests with fixes         |

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

<a href="https://www.loom.com/share/388d98aad1a04823b9ed50d0161a4819?sid=a2a669b4-f092-4067-adcb-c8527fbcaa90" target="_blank">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/388d98aad1a04823b9ed50d0161a4819-0ced91a0e8f80dcb-full-play.gif">
</a>


## Installation Options

Choose the installation method that works best for your environment:

<table width="100%">
  <tr valign="top">
    <td width="50%">
      <h3>Local CLI Installation</h3>
      <table>
        <tr>
          <td align="center" width="120">
            <a href="docs/installation.md#brew-maclinux">
              <img src="images/integration_logos/brew_logo.png" alt="Brew" width="50"><br>
              <strong>Brew(Mac/Linux)</strong>
            </a>
          </td>
          <td align="center" width="120">
            <a href="docs/installation.md#pip-and-pipx">
              <img src="images/integration_logos/pipx_logo.png" alt="pip" width="50"><br>
              <strong>pip/pipx</strong>
            </a>
          </td>
          <td align="center" width="120">
            <a href="docs/installation.md#docker-container">
              <img src="images/integration_logos/docker_logo.png" alt="Docker" width="50"><br>
              <strong>Docker</strong>
            </a>
          </td>
        </tr>
      </table>
    </td>
    <td width="50%">
      <h3>From Source Code</h3>
      <table>
        <tr>
          <td align="center" width="120">
            <a href="docs/installation.md#from-source-python-poetry">
              <img src="images/integration_logos/python_poetry_logo.png" alt="Python Poetry" width="50"><br>
              <strong>Python Poetry</strong>
            </a>
          </td>
          <td align="center" width="120">
            <a href="docs/installation.md#from-source-docker">
              <img src="images/integration_logos/docker_logo.png" alt="Docker Build" width="50"><br>
              <strong>Docker Build</strong>
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr valign="top">
    <td width="50%">
      <h3>In-Cluster Installation</h3>
      <table>
        <tr>
          <td align="center" width="120">
            <a href="docs/installation.md#in-cluster-installation-recommended">
              <img src="images/integration_logos/helm_logo.png" alt="Helm Chart" width="50"><br>
              <strong>Helm Chart</strong>
            </a>
          </td>
          <td align="center" width="120">
            <a href="https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section">
              <img src="images/integration_logos/robusta_logo.png" alt="Robusta SaaS" width="50"><br>
              <strong>Robusta SaaS</strong>
            </a>
          </td>
        </tr>
      </table>
    </td>
    <td width="50%">
      <h3>Other Options</h3>
      <table>
        <tr>
          <td align="center" width="120">
            <a href="docs/k9s.md">
              <img src="images/integration_logos/k9s_logo.png" alt="K9s Plugin" width="50"><br>
              <strong>K9s Plugin</strong>
            </a>
          </td>
          <td align="center" width="120">
            <a href="docs/python.md">
              <img src="images/integration_logos/python_logo.png" alt="Python Package" width="50"><br>
              <strong>Python Package</strong>
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>

For advanced use cases, you can [import HolmesGPT as a Python library](docs/python.md) and use it from your own code. Before doing so, we recommend install HolmesGPT SaaS or CLI (see above) to learn your way around.

## Supported LLM Providers

Select your LLM provider to see how to set up your API Key.

<table>
  <tr>
    <td align="center" width="120">
      <a href="docs/api-keys.md#openai">
        <img src="images/integration_logos/openai_logo.png" alt="OpenAI" width="50"><br>
        <strong>OpenAI</strong>
      </a>
    </td>
    <td align="center" width="120">
      <a href="docs/api-keys.md#anthropic">
        <img src="images/integration_logos/anthropic_logo.png" alt="Anthropic" width="50"><br>
        <strong>Anthropic</strong>
      </a>
    </td>
    <td align="center" width="120">
      <a href="docs/api-keys.md#aws-bedrock">
        <img src="images/integration_logos/aws_bedrock_logo.png" alt="AWS Bedrock" width="50"><br>
        <strong>AWS Bedrock</strong>
      </a>
    </td>
    <td align="center" width="120">
      <a href="docs/api-keys.md#google-vertex-ai">
        <img src="images/integration_logos/google_vertexai_logo.png" alt="Google Vertex AI" width="50"><br>
        <strong>Google Vertex AI</strong>
      </a>
    </td>
  </tr>
  <tr>
    <td align="center" width="120">
      <a href="docs/api-keys.md#gemini">
        <img src="images/integration_logos/gemini_logo.png" alt="Gemini" width="50"><br>
        <strong>Gemini</strong>
      </a>
    </td>
    <td align="center" width="120">
      <a href="docs/api-keys.md#ollama">
        <img src="images/integration_logos/ollama_logo.png" alt="Ollama" width="50"><br>
        <strong>Ollama</strong>
      </a>
    </td>
  </tr>
</table>

You can also use any OpenAI-compatible models, read [here](docs/api-keys.md) for instructions.

### Using HolmesGPT

- In the Robusta SaaS: Go to [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and use Holmes from your browser
- With HolmesGPT CLI: [setup an LLM API key](docs/api-keys.md) and ask Holmes a question 👇

```bash
holmes ask "what pods are unhealthy and why?"
```

You can also provide files as context:
```bash
holmes ask "summarize the key points in this document" -f ./mydocument.txt
```

You can also load the prompt from a file using the `--prompt-file` option:
```bash
holmes ask --prompt-file ~/long-prompt.txt

Enter interactive mode to ask follow-up questions:
```bash
holmes ask "what pods are unhealthy and why?" --interactive
# or
holmes ask "what pods are unhealthy and why?" -i
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
