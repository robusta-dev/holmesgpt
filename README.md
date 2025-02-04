<div align="center">
  <h1 align="center">Solve alerts faster with an AI Agent</h1>
  <h2 align="center">HolmesGPT - AI Agent for On-Call Engineers 🔥</h2>
  <p align="center">
    <a href="#ways-to-use-holmesgpt"><strong>Examples</strong></a> |
    <a href="#key-features"><strong>Key Features</strong></a> |
    <a href="#installation"><strong>Installation</strong></a> |
    <a href="https://www.youtube.com/watch?v=TfQfx65LsDQ"><strong>YouTube Demo</strong></a>
  </p>
</div>

Respond to alerts faster, by using AI to automatically:

* Fetch logs, traces, and metrics
* Decide if the problem is likely **application problem or infrastructure problem** (who should investigate first?)
* Find upstream root-causes

Using HolmesGPT, you can transform your existing alerts from this 👇

![Screenshot 2024-10-31 at 12 01 12 2](https://github.com/user-attachments/assets/931ebd71-ccd2-4b7b-969d-a061a99cec2d)

To this 👇

<div align="center">
  <img src="https://github.com/user-attachments/assets/238d385c-70b5-4f41-a3cd-b7785f49d74c" alt="Prometheus alert with AI investigation" width="500px" />
</div>

### Key Features
- **Automatic data collection:** HolmesGPT surfaces up the observability data you need to investigate
- **Secure:** *Read-only* access to data - respects RBAC permissions
- **Runbook automation and knowledge sharing:** Tell Holmes how you investigate today and it will automate it
- **Extensible:** Add your own data sources (tools) and Holmes will use them to investigate
- **Data Privacy:** Bring your own API key for any AI provider (OpenAI, Azure, AWS Bedrock, etc)
- **Integrates with your existing tools** including Prometheus, PagerDuty, OpsGenie, Jira, and more

### See it in Action

<a href="https://www.loom.com/share/4c55f395dbd64ef3b69670eccf961124">
<img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/4c55f395dbd64ef3b69670eccf961124-db2004995e8d621c-full-play.gif">
</a>

## Ways to Use HolmesGPT

<details>
<summary> Analyze your alerts in a free UI</summary>

Includes free use of the Robusta AI model.

![Screenshot 2024-10-31 at 11 40 09](https://github.com/user-attachments/assets/2e90cc7b-4b0a-4386-ab4f-0d36692b549c)


[Sign up for Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) (Kubernetes cluster required) or contact us about on-premise options.
</details>

<details>
<summary>Add root-cause-analysis to Prometheus alerts in Slack</summary>

Investigate Prometheus alerts right from Slack with the official [Robusta integration](https://docs.robusta.dev/holmes_chart_dependency/configuration/ai-analysis.html).

![342708962-e0c9ccde-299e-41d7-84e3-c201277a9ccb (1)](https://github.com/robusta-dev/holmesgpt/assets/494087/fd2451b0-b951-4798-af62-f69affac831e)

Or run HolmesGPT from the cli:

```bash
kubectl port-forward alertmanager-robusta-kube-prometheus-st-alertmanager-0 9093:9093 &
holmes investigate alertmanager --alertmanager-url http://localhost:9093
```

Note - if on Mac OS and using the Docker image, you will need to use `http://docker.for.mac.localhost:9093` instead of `http://localhost:9093`
</details>


<details>
<summary>Query observability data in human language</summary>

Via the Holmes CLI or [a free UI (video)](https://www.loom.com/share/3cdcd94ed6bc458888b338493b108d1d?t=0)

```bash
holmes ask "what pods are in crashloopbackoff in my cluster and why?"
```
</details>

<details>
<summary>OpsGenie Integration</summary>

```bash
holmes investigate opsgenie --opsgenie-api-key <PLACEHOLDER_APIKEY>
```

By default results are displayed in the CLI . Use `--update --opsgenie-team-integration-key <PLACEHOLDER_TEAM_KEY>` to get the results as a comment in the OpsGenie alerts. Refer to the CLI help for more info.

![OpsGenie](./images/opsgenie-holmes-update.png)
</details>


<details>
<summary>PagerDuty Integration</summary>

```bash
holmes investigate pagerduty --pagerduty-api-key <PLACEHOLDER_APIKEY>
```

By default results are displayed in the CLI. Use `--update --pagerduty-user-email <PLACEHOLDER_EMAIL>` to get the results as a comment in the PagerDuty issue. Refer to the CLI help for more info.

![PagerDuty](./images/pagerduty-holmes-update.png)
</details>

<details>
<summary>K9s Plugin</summary>

You can add HolmesGPT as a plugin for K9s to investigate why any Kubernetes resource is unhealthy.

Add the following contents to the K9s plugin file, typically `~/.config/k9s/plugins.yaml` on Linux and `~/Library/Application Support/k9s/plugins.yaml` on Mac. Read more about K9s plugins [here](https://k9scli.io/topics/plugins/) and check your plugin path [here](https://github.com/derailed/k9s?tab=readme-ov-file#k9s-configuration).

**Note**: HolmesGPT must be installed and configured for the K9s plugin to work.

Basic plugin to run an investigation on any Kubernetes object, using the shortcut `Shift + H`:

```yaml
plugins:
  holmesgpt:
    shortCut: Shift-H
    description: Ask HolmesGPT
    scopes:
      - all
    command: bash
    background: false
    confirm: false
    args:
      - -c
      - |
        holmes ask "why is $NAME of $RESOURCE_NAME in -n $NAMESPACE not working as expected"
        echo "Press 'q' to exit"
        while : ; do
        read -n 1 k <&1
        if [[ $k = q ]] ; then
        break
        fi
        done
```

Advanced plugin that lets you modify the questions HolmesGPT asks about the LLM, using the shortcut `Shift + O`. (E.g. you can change the question to "generate an HPA for this deployment" and the AI will follow those instructions and output an HPA configuration.)
```yaml
plugins:
  custom-holmesgpt:
    shortCut: Shift-Q
    description: Custom HolmesGPT Ask
    scopes:
      - all
    command: bash

      - |
        INSTRUCTIONS="# Edit the line below. Lines starting with '#' will be ignored."
        DEFAULT_ASK_COMMAND="why is $NAME of $RESOURCE_NAME in -n $NAMESPACE not working as expected"
        QUESTION_FILE=$(mktemp)

        echo "$INSTRUCTIONS" > "$QUESTION_FILE"
        echo "$DEFAULT_ASK_COMMAND" >> "$QUESTION_FILE"

        # Open the line in the default text editor
        ${EDITOR:-nano} "$QUESTION_FILE"

        # Read the modified line, ignoring lines starting with '#'
        user_input=$(grep -v '^#' "$QUESTION_FILE")
        echo running: holmes ask "\"$user_input\""

        holmes ask "$user_input"
        echo "Press 'q' to exit"
        while : ; do
        read -n 1 k <&1
        if [[ $k = q ]] ; then
        break
        fi
        done
```
</details>

<details>
<summary>Importing Holmes as a Python library and bringing your own LLM</summary>

You can use Holmes as a library and pass in your own LLM implementation. This is particularly useful if LiteLLM or the default Holmes implementation does not suit you.

See an example implementation [here](examples/custom_llm.py).

</details>

Like what you see? Discover [more use cases](#more-use-cases) or get started by [installing HolmesGPT](#installation).

## In-Cluster Installation (Recommended)

Install Holmes + [Robusta](https://github.com/robusta-dev/robusta) as a unified package:

- Analysis based on **GPT-4o** (no API key needed)
- Simple installation using `helm`
- Built-in integrations with **Prometheus alerts** and **Slack**
- Visualize Kubernetes issues on a timeline, and analyze them with Holmes in a single click

**Note:** Requires a Kubernetes cluster.

[Create a free Robusta UI account »](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=easy_install_in_cluster_section)

## More Installation methods

**Prerequisite:** <a href="#getting-an-api-key"> Get an API key for a supported LLM.</a>

**Installation Methods:**

<details>
  <summary>Brew (Mac/Linux)</summary>

1. Add our tap:

```sh
brew tap robusta-dev/homebrew-holmesgpt
```

2. Install holmesgpt:

```sh
brew install holmesgpt
```

3. Check that installation was successful. **This will take a few seconds on the first run - wait patiently.**:

```sh
holmes --help
```

4. Run holmesgpt:

```sh
holmes ask "what issues do I have in my cluster"
```
</details>


<details>
<summary>Prebuilt Docker Container</summary>

Run the prebuilt Docker container `docker.pkg.dev/genuine-flight-317411/devel/holmes`, with extra flags to mount relevant config files (so that kubectl and other tools can access AWS/GCP resources using your local machine's credentials)

```bash
docker run -it --net=host -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes ask "what pods are unhealthy and why?"
```
</details>

<details>

<summary>Cutting Edge (Pip and Pipx)</summary>

You can install HolmesGPT from the latest git version with pip or pipx.

We recommend using pipx because it guarantees that HolmesGPT is isolated from other python packages on your system, preventing dependency conflicts.

First [Pipx](https://github.com/pypa/pipx) (skip this step if you are using pip).

Then install HolmesGPT from git with either pip or pipx:

```
pipx install "https://github.com/robusta-dev/holmesgpt/archive/refs/heads/master.zip"
```

Verify that HolmesGPT was installed by checking the version:

```
holmes version
```

To upgrade HolmesGPT with pipx, you can run:

```
pipx upgrade holmesgpt
```
</details>

<details>

<summary>From Source (Python Poetry)</summary>

First [install poetry (the python package manager)](https://python-poetry.org/docs/#installing-with-the-official-installer)

```
git clone https://github.com/robusta-dev/holmesgpt.git
cd holmesgpt
poetry install --no-root
poetry run python3 holmes.py ask "what pods are unhealthy and why?"
```
</details>

<details>
<summary>From Source (Docker)</summary>

Clone the project from github, and then run:

```bash
cd holmesgpt
docker build -t holmes . -f Dockerfile.dev
docker run -it --net=host -v -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config holmes ask "what pods are unhealthy and why?"
```
</details>

<details>
<summary>Run HolmesGPT in your cluster (Helm)</summary>

Most users should install Holmes using the instructions in the [Robusta docs ↗](https://docs.robusta.dev/master/configuration/ai-analysis.html) and NOT the instructions below.

By using the `Robusta` integration, you’ll benefit from a fully integrated setup that works seamlessly with `Prometheus alerts` and `Slack`. Using the instructions below requires you to build and configure many of these components yourself.

### Environment Variable Configuration

In this mode, all parameters should be passed to the HolmesGPT deployment using environment variables. To securely manage sensitive data, we recommend pulling sensitive variables from Kubernetes `secrets`.

#### Example Configuration
Create a `holmes-values.yaml` file with your desired environment variables:

```yaml
additionalEnvVars:
  - name: MODEL
    value: gpt-4o
  - name: OPENAI_API_KEY
    value: <your open ai key>
```

Install Holmes with Helm:

```bash
helm repo add robusta https://robusta-charts.storage.googleapis.com && helm repo update
helm install holmes robusta/holmes -f holmes-values.yaml
```

For all LLMs, you must provide the `MODEL` environment variable, which specifies the model you are using. Some LLMs may require additional variables.

### Using `{{ env.VARIABLE_NAME }}` for Secrets

For enhanced security and flexibility, you can substitute values directly with environment variables using the `{{ env.VARIABLE_NAME }}` syntax. This is especially useful for passing sensitive information like API keys or credentials.

Example configuration for OpenSearch integration:

```yaml
toolsets:
  opensearch:
    enabled: true
    config:
      # OpenSearch configuration
      opensearch_clusters:
        - hosts:
            - host: "{{ env.OPENSEARCH_URL }}"
              port: 9200
          headers:
            Authorization: "Basic {{ env.OPENSEARCH_BEARER_TOKEN }}"
          # Additional parameters
          use_ssl: true
          ssl_assert_hostname: false
          verify_certs: false
          ssl_show_warn: false
```

In this example:
- `{{ env.OPENSEARCH_URL }}` will be replaced by the `OPENSEARCH_URL` environment variable.
- `{{ env.OPENSEARCH_BEARER_TOKEN }}` will pull the value of the `OPENSEARCH_BEARER_TOKEN` environment variable.

This approach allows sensitive variables to be managed securely, such as by using Kubernetes secrets.

### Custom Toolset Configurations

You can also add custom configurations for other toolsets. For example:

```yaml
toolsets:
  tool_name_here:
    enabled: true
    config:
      # Custom configuration for your tool
      custom_param: "{{ env.CUSTOM_PARAM }}"
```

This structure enables you to add or modify toolset configurations easily, while leveraging environment variables for flexibility and security.

<details>
<summary>OpenAI</summary>

For OpenAI, only the ``model`` and ``api-key`` should be provided

    additionalEnvVars:
    - name: MODEL
      value: gpt-4o
    - name: OPENAI_API_KEY
      valueFrom:
        secretKeyRef:
          name: my-holmes-secret
          key: openAiKey

**Note**: ``gpt-4o`` is optional since it's default model.

</details>

<details>
<summary>Azure OpenAI</summary>

To work with Azure AI, you need to provide the below variables:

    additionalEnvVars:
    - name: MODEL
      value: azure/my-azure-deployment         # your azure deployment name
    - name: AZURE_API_VERSION
      value: 2024-02-15-preview                # azure openai api version
    - name: AZURE_API_BASE
      value: https://my-org.openai.azure.com/  # base azure openai url
    - name: AZURE_API_KEY
      valueFrom:
        secretKeyRef:
          name: my-holmes-secret
          key: azureOpenAiKey

</details>

<details>
<summary>AWS Bedrock</summary>

    enablePostProcessing: true
    additionalEnvVars:
    - name: MODEL
      value: bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
    - name: AWS_REGION_NAME
      value: us-east-1
    - name: AWS_ACCESS_KEY_ID
      valueFrom:
        secretKeyRef:
          name: my-holmes-secret
          key: awsAccessKeyId
    - name: AWS_SECRET_ACCESS_KEY
      valueFrom:
        secretKeyRef:
          name: my-holmes-secret
          key: awsSecretAccessKey

**Note**: ``bedrock claude`` provides better results when using post-processing to summarize the results.
</details>


</details>

### Getting an API Key

HolmesGPT requires an LLM API Key to function. The most common option is OpenAI, but many [LiteLLM-compatible](https://docs.litellm.ai/docs/providers/) models are supported. To use an LLM, set `--model` (e.g. `gpt-4o` or `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0`) and `--api-key` (if necessary). Depending on the provider, you may need to set environment variables too.

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
<summary>Confluence</summary>
HolmesGPT can read runbooks from Confluence. To give it access, set the following environment variables:

* `CONFLUENCE_BASE_URL` - e.g. https://robusta-dev-test.atlassian.net
* `CONFLUENCE_USER` - e.g. user@company.com
* `CONFLUENCE_API_KEY` - [refer to Atlassian docs on generating API keys](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/)
</details>

<details>
<summary>
Jira, GitHub, OpsGenie, PagerDuty, and AlertManager
</summary>

HolmesGPT can pull tickets/alerts from each of these sources and investigate them.

Refer to `holmes investigate jira --help` etc for details.
</details>


<details>
<summary>
Fetching runbooks through URLs
</summary>

HolmesGPT can consult webpages containing runbooks or other relevant information.
This is done through a HTTP GET and the resulting HTML is then cleaned and parsed into markdown.
Any Javascript that is on the webpage is ignored.
</details>

<details>
<summary>
Using Grafana Loki
</summary>

HolmesGPT can consult logs from [Loki](https://grafana.com/oss/loki/) by proxying through a [Grafana](https://grafana.com/oss/grafana/) instance.

To configure loki toolset:

```yaml
toolsets:
  grafana/loki:
    enabled: true
    config:
      api_key: "{{ env.GRAFANA_API_KEY }}"
      url: "http://loki-url"
```

For search terms, you can optionally tweak the search terms used by the toolset.
This is done by appending the following to your Holmes grafana/loki configuration:

```yaml
pod_name_search_key: "pod"
namespace_search_key: "namespace"
node_name_search_key: "node"
```

> You only need to tweak the configuration file if your Loki logs settings for pod, namespace and node differ from the above defaults.

</details>

<details>
<summary>
Using Grafana Tempo
</summary>

HolmesGPT can fetch trace information from Grafana Tempo to debug performance related issues.

Tempo is configured the using the same Grafana settings as the Grafana Loki toolset.

</details>


<details>
<summary>
ArgoCD
</summary>

Holmes can use the `argocd` CLI to get details about the ArgoCD setup like the apps configuration and status, clusters and projects within ArgoCD.
To enable ArgoCD, set the `ARGOCD_AUTH_TOKEN` environment variable as described in the [argocd documentation](https://argo-cd.readthedocs.io/en/latest/user-guide/commands/argocd_account_generate-token/).

</details>

## More Use Cases

HolmesGPT was designed for incident response, but it is a general DevOps assistant too. Here are some examples:

<details>
<summary>Ask Questions About Your Cloud</summary>

```bash
holmes ask "what services does my cluster expose externally?"
```
</details>

<details>
<summary>Ticket Management - Automatically Respond to Jira tickets related to DevOps tasks</summary>

```bash
holmes investigate jira  --jira-url https://<PLACEDHOLDER>.atlassian.net --jira-username <PLACEHOLDER_EMAIL> --jira-api-key <PLACEHOLDER_API_KEY>
```
</details>

<details>
<summary>Find the right configuration to change in big Helm charts</summary>

LLM uses the built-in [Helm toolset](./holmes/plugins/toolsets/helm.yaml) to gather information.

```bash
holmes ask "what helm value should I change to increase memory request of the my-argo-cd-argocd-server-6864949974-lzp6m pod"
```
</details>

<details>
<summary>Optimize Docker container size</summary>

LLM uses the built-in [Docker toolset](./holmes/plugins/toolsets/docker.yaml) to gather information.

```bash
holmes ask "Tell me what layers of my pavangudiwada/robusta-ai docker image consume the most storage and suggest some fixes to it"
```
</details>

## Customizing HolmesGPT

HolmesGPT can investigate many issues out of the box, with no customization or training.

That said, we provide several extension points for teaching HolmesGPT to investigate your issues, according to your best practices. The two main extension points are:

* Custom Tools - give HolmesGPT access to data that it can't otherwise access - e.g. traces, APM data, or custom APIs
* Custom Runbooks - give HolmesGPT instructions for investigating specific issues it otherwise wouldn't know how to handle

<details>
<summary>Add Custom Tools</summary>

The more data you give HolmesGPT, the better it will perform. Give it access to more data by adding custom tools.

New tools are loaded using `-t` from [custom toolset files](./examples/custom_toolset.yaml) or by adding them to the `~/.holmes/config.yaml` with the setting `custom_toolsets: ["/path/to/toolset.yaml"]`.
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

By default, without specifying `--config` the agent will try to read `~/.holmes/config.yaml`. When settings are present in both config file and cli, the cli option takes precedence.


<details>
<summary>Custom Toolsets</summary>

You can define your own custom toolsets to extend the functionality of your setup. These toolsets can include querying company-specific data, fetching logs from observability tools, and more.

```bash
# Add paths to your custom toolsets here
# Example: ["path/to/your/custom_toolset.yaml"]
#custom_toolsets: ["examples/custom_toolset.yaml"]
```
</details>

<details>

<summary>Alertmanager Configuration</summary>

Configure the URL for your Alertmanager instance to enable alert management and notifications.

```bash
# URL for the Alertmanager
#alertmanager_url: "http://localhost:9093"
```
</details>

<details>

<summary>Jira Integration</summary>

Integrate with Jira to automate issue tracking and project management tasks. Provide your Jira credentials and specify the query to fetch issues and optionally update their status.

```bash
# Jira credentials and query settings
#jira_username: "user@company.com"
#jira_api_key: "..."
#jira_url: "https://your-company.atlassian.net"
#jira_query: "project = 'Natan Test Project' and Status = 'To Do'"
```

1. **jira_username**: The email you use to log into your Jira account. Eg: `jira-user@company.com`
2. **jira_api_key**: Follow these [instructions](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/) to get your API key.
3. **jira_url**: The URL of your workspace. For example: [https://workspace.atlassian.net](https://workspace.atlassian.net) (**Note:** schema (https) is required)
4. **project**: Name of the project you want the Jira tickets to be created in. Go to **Project Settings** -> **Details** -> **Name**.
5. **status**: Status of a ticket. Example: `To Do`, `In Progress`
</details>

<details>

<summary>GitHub Integration</summary>

Integrate with GitHub to automate issue tracking and project management tasks. Provide your GitHub PAT (*personal access token*) and specify the `owner/repository`.

```bash
# GitHub credentials and query settings
#github_owner: "robusta-dev"
#github_pat: "..."
#github_url: "https://api.github.com" (default)
#github_repository: "holmesgpt"
#github_query: "is:issue is:open"
```

1. **github_owner**: The repository owner. Eg: `robusta-dev`
2. **github_pat**: Follow these [instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) to get your GitHub pat (*personal access token*).
3. **github_url**: The URL of your GitHub API. For example: [https://api.github.com](https://api.github.com) (**Note:** schema (https) is required)
4. **github_repository**: Name of the repository you want the GitHub issues to be scanned. Eg: `holmesgpt`.
</details>

<details>
<summary>PagerDuty Integration</summary>

Integrate with PagerDuty to automate incident tracking and project management tasks. Provide your PagerDuty credentials and specify the user email to update the incident with findings.

```bash
pagerduty_api_key: "..."
pagerduty_user_email: "user@mail.com"
pagerduty_incident_key:  "..."
```

1. **pagerduty_api_key**: The PagerDuty API key.  This can be found in the PagerDuty UI under Integrations > API Access Key.
2. **pagerduty_user_email**: When --update is set, which user will be listed as the user who updated the incident. (Must be the email of a valid user in your PagerDuty account.)
3. **pagerduty_incident_key**: If provided, only analyze a single PagerDuty incident matching this key
</details>

<details>
<summary>OpsGenie Integration</summary>

Integrate with OpsGenie to automate alert investigations. Provide your OpsGenie credentials and specify the query to fetch alerts.

```bash
opsgenie_api_key : "..."
opsgenie-team-integration-key: "...."
opsgenie-query: "..."
```

1. **opsgenie_api_key**: The OpsGenie API key. Get it from Settings > API key management > Add new API key
2. **opsgenie-team-integration-key**: OpsGenie Team Integration key for writing back results. (NOT a normal API Key.) Get it from Teams > YourTeamName > Integrations > Add Integration > API Key. Don't forget to turn on the integration and add the Team as Responders to the alert.
3. **opsgenie-query**: E.g. 'message: Foo' (see https://support.atlassian.com/opsgenie/docs/search-queries-for-alerts/)
</details>


<details>

<summary>Slack Integration</summary>

Configure Slack to send notifications to specific channels. Provide your Slack token and the desired channel for notifications.

```bash
# Slack token and channel configuration
#slack_token: "..."
#slack_channel: "#general"
```

1. **slack-token**: The Slack API key. You can generate with `pip install robusta-cli && robusta integrations slack`
2. **slack-channel**: The Slack channel where you want to receive the findings.

</details>


<details>
<summary>OpenSearch Integration</summary>

The OpenSearch toolset (`opensearch`) allows Holmes to consult an opensearch cluster for its health, settings and shards information.
The toolset supports multiple opensearch or elasticsearch clusters that are configured by editing Holmes' configuration file:

```
opensearch_clusters:
  - hosts:
      - https://my_elasticsearch.us-central1.gcp.cloud.es.io:443
    headers:
      Authorization: "ApiKey <your_API_key>"
# or
#  - hosts:
#      - https://my_elasticsearch.us-central1.gcp.cloud.es.io:443
#    http_auth:
#      username: ELASTIC_USERNAME
#      password: ELASTIC_PASSWORD
```

The configuration for each OpenSearch cluster is passed directly to the [opensearch-py](https://github.com/opensearch-project/opensearch-py) module. Refer to the module's documentation for detailed guidance on configuring connectivity.

To enable OpenSearch integration when running HolmesGPT in a Kubernetes cluster, **include the following configuration** in the `Helm chart`:

```yaml
toolsets:
  opensearch:
    enabled: true
    config:
      # OpenSearch configuration
      opensearch_clusters:
        - hosts:
            - host: "{{ env.OPENSEARCH_URL }}"
              port: 9200
          headers:
            Authorization: "Basic {{ env.OPENSEARCH_BEARER_TOKEN }}"
          # Additional parameters
          use_ssl: true
          ssl_assert_hostname: false
          verify_certs: false
          ssl_show_warn: false
```

</details>


<details>

<summary>Custom Runbooks</summary>

Define custom runbooks to give explicit instructions to the LLM on how to investigate certain alerts. This can help in achieving better results for known alerts.

```bash
# Add paths to your custom runbooks here
# Example: ["path/to/your/custom_runbook.yaml"]
#custom_runbooks: ["examples/custom_runbooks.yaml"]
```
</details>

### Large Language Model (LLM) Configuration

Choose between OpenAI, Azure, AWS Bedrock, and more. Provide the necessary API keys and endpoints for the selected service.


<details>

<summary>OpenAI</summary>

```bash
# Configuration for OpenAI LLM
#api_key: "your-secret-api-key"
```
</details>

<details>

<summary>Azure</summary>

```bash
# Configuration for Azure LLM
#api_key: "your-secret-api-key"
#model: "azure/<DEPLOYMENT_NAME>"
#you will also need to set environment variables - see above
```
</details>

<summary>Bedrock</summary>

```bash
# Configuration for AWS Bedrock LLM
#model: "bedrock/<MODEL_ID>"
#you will also need to set environment variables - see above
```
</details>

</details>

## License

Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/holmesgpt/blob/master/LICENSE.txt) for more information.
<!-- Change License -->

## Support

If you have any questions, feel free to message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)

## How to Contribute

To contribute to HolmesGPT, first follow the <a href="#installation"><strong>Installation</strong></a> instructions for **running HolmesGPT from source using Poetry.** Then follow an appropriate guide below, or ask us for help on [Slack](https://bit.ly/robusta-slack)

<details>
<summary>Adding new runbooks</summary>

You can contribute knowledge on solving common alerts and HolmesGPT will use this knowledge to solve related issues. To do so, add a new file to [./holmes/plugins/runbooks](holmes/plugins/runbooks) - or edit an existing runbooks file in that same directory.

Note: if you prefer to keep your runbooks private, you can store them locally and pass them to HolmesGPT with the `-r` flag. However, if your runbooks relate to common problems that others may encounter, please consider opening a PR and making HolmesGPT better for everyone!

</details>

<details>
<summary>Adding new toolsets</summary>

You can add define new tools in YAML and HolmesGPT will use those tools in it's investigation. To do so, add a new file to [./holmes/plugins/toolsets](holmes/plugins/toolsets) - or edit an existing toolsets file in that same directory.

Note: if you prefer to keep your tools private, you can store them locally and pass them to HolmesGPT with the `-t` flag. However, please consider contributing your toolsets! At least one other community member will probably find them useful!

</details>

<details>
<summary>Modifying the default prompts (prompt engineering)</summary>

The default prompts for HolmesGPT are located in [./holmes/plugins/prompts](holmes/plugins/prompts). Most `holmes` commands accept a `--system-prompt` flag that you can use to override this.

If you find a scenario where the default prompts don't work, please consider letting us know by opening a GitHub issue or messaging us on Slack! We have an internal evaluation framework for benchmarking prompts on many troubleshooting scenarios and if you share a case where HolmesGPT doesn't work, we will be able to add it to our test framework and fix the performance on that issue and similar ones.

</details>

<details>
<summary>Adding new data sources</summary>

If you want HolmesGPT to investigate external tickets or alert, you can add a new datasource. This requires modifying the source code and opening a PR. [You can see an example PR like that here, which added support for investigating GitHub issues](https://github.com/robusta-dev/holmesgpt/pull/28/files).

</details>
