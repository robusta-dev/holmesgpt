<div align="center">
  <h1 align="center">HolmesGPT - The Open Source On-Call/DevOps Assistant</h1>
<h2 align="center">Get a head start on fixing alerts with AI investigation</h2>
  <p align="center">
    <a href="#examples"><strong>Examples</strong></a> |
    <a href="#key-features"><strong>Key Features</strong></a> |
    <a href="#installation"><strong>Installation</strong></a> 
  </p>
</div>

The only AI assistant that investigates incidents **like a human does** - by looking at alerts and fetching missing data until it finds the root cause. Powered by OpenAI or any tool-calling LLM of your choice, including open source models.

### What Can HolmesGPT Do?
- **Investigate Incidents (AIOps)** from PagerDuty/OpsGenie/Prometheus/Jira/more
- **Automated Triage:** Use HolmesGPT as a first responder. Flag critical alerts and prioritize them for your team to look at
- **Alert Enrichment:** Automatically add context to alerts - like logs and microservice health info - to find root causes faster   
- **Identify Cloud Problems** by asking HolmesGPT questions about unhealthy infrastructure
- **Runbook Automation in Plain English:** HolmesGPT can speed up your response to known issues by investigating according to runbooks you provide

### See it in Action
![AI Alert Analysis](images/holmesgptdemo.gif)

## Examples

<details>
<summary>Investigate a Kubernetes Problem</summary>

```bash
holmes ask "what pods are unhealthy in my cluster and why?"
```
</details>

<details>
<summary>Investigate a Firing Prometheus alert</summary>

```bash
kubectl port-forward alertmanager-robusta-kube-prometheus-st-alertmanager-0 9093:9093 &
holmes investigate alertmanager --alertmanager-url http://localhost:9093
```

Note - if on Mac OS and using the Docker image, you will need to use `http://docker.for.mac.localhost:9093` instead of `http://localhost:9093`
</details>

<details>

<summary>Investigate and update Jira tickets with findings</summary>

```bash
holmes investigate jira --jira-url https://<PLACEDHOLDER>.atlassian.net --jira-username <PLACEHOLDER_EMAIL> --jira-api-key <PLACEHOLDER_API_KEY>
```

By default Jira investigation results are displayed in the CLI itself. But you can use `--update-ticket` to get the results as a comment in the Jira ticket.


</details>

<details>
<summary>Investigate and update GitHub Issues with findings</summary>

```bash
holmes investigate github --github-url https://<PLACEHOLDER> --github-owner <PLACEHOLDER_OWNER_NAME> --github-repository <PLACEHOLDER_GITHUB_REPOSITORY> --github-pat <PLACEHOLDER_GITHUB_PAT>
```

By default GitHub investigation results are displayed in the CLI itself. But you can use `--update-issue` to get the results as a comment in the GitHub issue.

</details>

Like what you see? Checkout [other use cases](#other-use-cases) or get started by [installing HolmesGPT](#installation).

## Key Features
- **Connects to Existing Observability Data:** Find correlations you didn’t know about. No need to gather new data or add instrumentation.
- **Compliance Friendly:** Can be run on-premise with your own LLM (or in the cloud with OpenAI or Azure)
- **Transparent Results:** See a log of the AI’s actions and what data it gathered to understand how it reached conclusions
- **Extensible Data Sources:** Connect the AI to custom data by providing your own tool definitions
- **Runbook Automation:** Optionally provide runbooks in plain English and the AI will follow them automatically
- **Integrates with Existing Workflows:** Connect Slack and Jira to get results inside your existing tools

## Installation

First you will need <a href="#getting-an-api-key">an OpenAI API key, or the equivalent for another model</a>. Then install with one of the below methods:

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

Run the below command, replacing `<VERSION_PLACEHOLDER>` with the latest HolmesGPT version - e.g. `0.1`.

```bash
docker run -it --net=host -v $(pwd)/config.yaml:/app/config.yaml -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes:<VERSION_PLACEHOLDER> ask "what pods are unhealthy and why?"
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
docker build -t holmes .
docker run -it --net=host -v $(pwd)/config.yaml:/app/config.yaml -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config holmest ask "what pods are unhealthy and why?"
```
</details>


### Getting an API Key

HolmesGPT requires an API Key to function. Follow one of the instructions below.

<details>
<summary>OpenAI</summary>
  
To work with OpenAI’s GPT 3.5 or GPT-4 models you need a paid [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).

**Note**: This is different from being a “ChatGPT Plus” subscriber.

Add the `api_key` to the config.yaml or pass via the CLI with --api-key.
</details>

<details>
<summary>Azure OpenAI</summary>

To work with Azure AI, you need the [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource). 

```bash
holmes ask "what pods are unhealthy and why?" --llm=azure --api-key=<PLACEHOLDER> --azure-endpoint='<PLACEHOLDER>'
```

</details>

<details>
<summary>Using a self-hosted LLM</summary>

You will need an LLM with support for function-calling (tool-calling). To use it, set the OPENAI_BASE_URL environment variable and run `holmes` with a relevant model name set using `--model`.

**Important: Please verify that your model and inference server support function calling! HolmesGPT is currently unable to check if the LLM it was given supports function-calling or not. Some models that lack function-calling capabilities will  hallucinate answers instead of reporting that they are unable to call functions. This behaviour depends on the model.**

In particular, note that [vLLM does not yet support function calling](https://github.com/vllm-project/vllm/issues/1869), whereas [llama-cpp does support it](https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#function-calling).

</details>

## Other Use Cases

HolmesGPT is usually used for incident response, but it can function as a general-purpose DevOps assistant too. Here are some examples:

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


## Advanced Usage

<details>
<summary>Add Custom Tools</summary>

The more data you give HolmesGPT, the better it will perform. Give it access to more data by adding custom tools.

New tools are loaded using `-t` from [custom toolset files](./examples/custom_toolset.yaml) or by adding them to the `config.yaml` in `custom_toolsets`.
</details>

<details>
<summary>Add Custom Runbooks</summary>

HolmesGPT can investigate by following runbooks written in plain English. Add your own runbooks to provided the LLM specific instructions.

New runbooks are loaded using `-r` from [custom runbook files](./examples/custom_runbook.yaml) or by adding them to the `config.yaml` in `custom_runbooks`.
</details>

<details>
<summary>Reading settings from a config file</summary>

You can customize HolmesGPT's behaviour with command line flags, or you can save common settings in config file for re-use.

You can view an example config file with all available settings [here](config.example.yaml).

By default, without specifying `--config` the agent will try to read `config.yaml` from the current directory.
If a setting is specified in both in config file and cli, cli takes precedence.



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

<summary>Custom Runbooks</summary>

Define custom runbooks to give explicit instructions to the LLM on how to investigate certain alerts. This can help in achieving better results for known alerts.

```bash
# Add paths to your custom runbooks here
# Example: ["path/to/your/custom_runbook.yaml"]
#custom_runbooks: ["examples/custom_runbooks.yaml"]
```
</details>

### Large Language Model (LLM) Configuration

Choose between OpenAI or Azure for integrating large language models. Provide the necessary API keys and endpoints for the selected service.


<details>

<summary>OpenAI</summary>

```bash
# Configuration for OpenAI LLM
#llm: "openai"
#api_key: "..."
```
</details>

<details>

<summary>Azure</summary>

```bash
# Configuration for Azure LLM
#llm: "azure"
#api_key: "..."
#azure_endpoint: "..."
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
