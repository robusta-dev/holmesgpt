<div align="center">
  <h1 align="center">Solve alerts faster with an AI Agent</h1>
  <p align="center">
    <a href="#ways-to-use-holmesgpt"><strong>Examples</strong></a> |
    <a href="#key-features"><strong>Key Features</strong></a> |
    <a href="#installation"><strong>Installation</strong></a> |
    <a href="https://www.youtube.com/watch?v=TfQfx65LsDQ"><strong>YouTube Demo</strong></a>
  </p>
</div>

HolmesGPT transforms your on-call experience by automatically:
- Fetching relevant logs, traces, and metrics
- Determining if issues are application or infrastructure related
- Identifying upstream root causes
- Providing actionable insights

### Before & After

Send HolmesGPT traditional alerts like this 👇 

![Before HolmesGPT](https://github.com/user-attachments/assets/931ebd71-ccd2-4b7b-969d-a061a99cec2d)

And get this 👇

<div align="center">
  <img src="https://github.com/user-attachments/assets/238d385c-70b5-4f41-a3cd-b7785f49d74c" alt="Prometheus alert with AI investigation" width="500px" />
</div>


### Key Features
🔍 **Automatic Data Collection**
- Surfaces relevant observability data for investigation
- Integrates with your existing monitoring stack

🔒 **Enterprise-Ready**
- Read-only data access - respects RBAC permissions
- Bring your own API key (OpenAI, Azure, AWS Bedrock, etc.)
- Privacy-focused design - can keep all data in your cloud account

🚀 **Powerful Integrations**
- Works with Prometheus, PagerDuty, OpsGenie, Jira, and more
- Extensible plugin system for custom data sources
- Connect to knowledge-bases and existing runbooks in Confluence

### See it in Action

<a href="https://www.loom.com/share/4c55f395dbd64ef3b69670eccf961124">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/4c55f395dbd64ef3b69670eccf961124-db2004995e8d621c-full-play.gif">
</a>

## Quick Start

If you use Kubernetes, we recommend installing Holmes + [Robusta](https://github.com/robusta-dev/robusta) as a unified package. This will let you:

- Analyze alerts in a web UI and ask follow-up questions
- Use natural language to query observability and K8s data in a ChatGPT-like interface
- Easily integrate Holmes with **Prometheus alerts**, [Slack](https://docs.robusta.dev/master/configuration/ai-analysis.html), and more
- Use Holmes immediately without needing an OpenAI API Key (but you can bring one if you prefer!)
- Install HolmesGPT quickly with `helm`

[Sign up for Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) or contact us about on-premise options.


## More Installation methods

Holmes can be installed as a local CLI using: 

* Brew
* Docker
* Pip/Pipx
* Building from source

See [Additional Installation Options](docs/installation.md).

## Using HolmesGPT

If you installed Robusta + HolmesGFPT, go to [platform.robusta.dev](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) and use Holmes from your browser.

If you installed HolmesGPT as a CLI tool, you'll need to first [setup an API key](#getting-an-api-key). Then ask Holmes a question:

```bash
holmes ask "what pods are unhealthy and why?"
```

To investigate Prometheus alerts with the CLI:

```bash
kubectl port-forward alertmanager-robusta-kube-prometheus-st-alertmanager-0 9093:9093 &
holmes investigate alertmanager --alertmanager-url http://localhost:9093
# if on Mac OS and using the Holmes Docker image👇
#  holmes investigate alertmanager --alertmanager-url http://docker.for.mac.localhost:9093
```

To investigate alerts from your on-call tools:

```bash
holmes investigate opsgenie --opsgenie-api-key <OPSGENIE_API_KEY>
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY>
# to write the analysis back to the incident as a comment
holmes investigate pagerduty --pagerduty-api-key <PAGERDUTY_API_KEY> --update
```

Finally, you can add HolmesGPT as a [K9s plugin](docs/k9s.md) to quickly run investigations on Kubernetes resources.

### Getting an API Key

If you use HolmesGPT + Robusta SaaS, you can start using HolmesGPT right away, without an API Key like OpenAI.

If you're running HolmesGPT standalone or would like to configure an API key with Robusta SaaS for data-privacy reasons, see below. 

The most popular LLM provider is OpenAI, but you can use most [LiteLLM-compatible](https://docs.litellm.ai/docs/providers/) AI models with HolmesGPT. To use an LLM, set `--model` (e.g. `gpt-4o` or `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0`) and `--api-key` (if necessary). Depending on the provider, you may need to set environment variables too.

**Instructions for popular LLMs:**

<details>
<summary>OpenAI</summary>

To work with OpenAI’s GPT 3.5 or GPT-4 models you need a paid [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).

**Note**: This is different from being a “ChatGPT Plus” subscriber.

Pass your API key to holmes with the `--api-key` cli argument. Because OpenAI is the default LLM, the `--model` flag is optional for OpenAI (gpt-4o is the default).

```
holmes ask --api-key="..." "what pods are crashing in my cluster and why?"
```

If you prefer not to pass secrets on the cli, set the OPENAI_API_KEY environment variable or save the API key in a HolmesGPT config file.

</details>

<details>
<summary>Azure OpenAI</summary>

To work with Azure AI, you need an [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource) and to set the following environment variables:

* AZURE_API_VERSION - e.g. 2024-02-15-preview
* AZURE_API_BASE - e.g. https://my-org.openai.azure.com/
* AZURE_API_KEY (optional) - equivalent to the `--api-key` cli argument

Set those environment variables and run:

```bash
holmes ask "what pods are unhealthy and why?" --model=azure/<DEPLOYMENT_NAME> --api-key=<API_KEY>
```

Refer [LiteLLM Azure docs ↗](https://litellm.vercel.app/docs/providers/azure) for more details.
</details>

<details>
<summary>AWS Bedrock</summary>

Before running the below command you must run `pip install boto3>=1.28.57` and set the following environment variables:

* `AWS_REGION_NAME`
* `AWS_ACCESS_KEY_ID`
* `AWS_SECRET_ACCESS_KEY`

If the AWS cli is already configured on your machine, you may be able to find those parameters with:

```console
cat ~/.aws/credentials ~/.aws/config
```

Once everything is configured, run:
```console
holmes ask "what pods are unhealthy and why?" --model=bedrock/<MODEL_NAME>
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g. `anthropic.claude-3-5-sonnet-20240620-v1:0`. To list models your account can access:

```
aws bedrock list-foundation-models --region=us-east-1
```

Note that different models are available in different regions. For example, Claude Opus is only available in us-west-2.

Refer to [LiteLLM Bedrock docs ↗](https://litellm.vercel.app/docs/providers/bedrock) for more details.
</details>

<details>
<summary>Using Ollama</summary>
Ollama is supported, but buggy. We recommend using other models if you can, until Ollama tool-calling capabilities improve.
Specifically, Ollama often calls tools with non-existent or missing parameters.

If you'd like to try using Ollama anyway, see below:
```
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are unhealthy in my cluster?" --model="ollama_chat/llama3.1"
```

You can also connect to Ollama in the standard OpenAI format (this should be equivalent to the above):

```
# note the v1 at the end
export OPENAI_API_BASE="http://localhost:11434/v1"
# holmes requires OPENAPI_API_KEY to be set but value does not matter
export OPENAI_API_KEY=123
holmes ask "what pods are unhealthy in my cluster?" --model="openai/llama3.1"
```

</details>
<details>
<summary>Gemini/Google AI Studio</summary>

To use Gemini, set the `GEMINI_API_KEY` environment variable as follows:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

Once the environment variable is set, you can run the following command to interact with Gemini:

```bash
holmes ask "what pods are unhealthy and why?" --model=gemini/<MODEL_NAME>
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g., `gemini-pro`,`gemini/gemini-1.5-flash`, etc.

</details>
<details>
<summary>Vertex AI Gemini</summary>

To use Vertex AI with Gemini models, set the following environment variables:

```bash
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service_account_key.json"
```

Once the environment variables are set, you can run the following command to interact with Vertex AI Gemini models:

```bash
poetry run python holmes.py ask "what pods are unhealthy and why?" --model "vertex_ai/<MODEL_NAME>"
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g., `gemini-pro`,`gemini-2.0-flash-exp`, etc.
Ensure you have the correct project, location, and credentials for accessing the desired Vertex AI model.

</details>
<details>
<summary>Using other OpenAI-compatible models</summary>

You will need an LLM with support for function-calling (tool-calling).

* Set the environment variable for your URL with `OPENAI_API_BASE`
* Set the model as `openai/<your-model-name>` (e.g., `llama3.1:latest`)
* Set your API key (if your URL doesn't require a key, then add a random value for `--api-key`)

```bash
export OPENAI_API_BASE=<URL_HERE>
holmes ask "what pods are unhealthy and why?" --model=openai/<MODEL_NAME> --api-key=<API_KEY_HERE>
```

**Important: Please verify that your model and inference server support function calling! HolmesGPT is currently unable to check if the LLM it was given supports function-calling or not. Some models that lack function-calling capabilities will  hallucinate answers instead of reporting that they are unable to call functions. This behaviour depends on the model.**

In particular, note that [vLLM does not yet support function calling](https://github.com/vllm-project/vllm/issues/1869), whereas [llama-cpp does support it](https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#function-calling).

</details>

**Additional LLM Configuration:**

<details>
<summary>Trusting custom Certificate Authority (CA) certificate</summary>
If your llm provider url uses a certificate from a custom CA, in order to trust it, base-64 encode the certificate, and store it in an environment variable named <b>CERTIFICATE</b>
</details>

### Enabling Integrations

<details>
<summary>
Jira, GitHub, OpsGenie, PagerDuty, and AlertManager
</summary>

HolmesGPT can pull tickets/alerts from each of these sources and investigate them.

Refer to `holmes investigate jira --help` etc for details.
</details>


<details>
<summary>
Builtin toolsets
</summary>

HolmesGPT has a number of toolsets that give it access to many datasources. This enhances HolmesGPT's ability to get to the root cause of issues.

These toolsets are documented on [Robusta's documentation for builtin toolsets](https://docs.robusta.dev/master/configuration/holmesgpt/builtin_toolsets.html),
although this documentation applies to running Holmes in clusters and not with the CLI.
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

</defails>

## License
Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/holmesgpt/blob/master/LICENSE.txt) for more information.
<!-- Change License -->

## Support

If you have any questions, feel free to message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)

## How to Contribute

To contribute to HolmesGPT, first follow the <a href="#installation"><strong>Installation</strong></a> instructions for **running HolmesGPT from source using Poetry.** Feel free to ask us for help on [Slack](https://bit.ly/robusta-slack)
