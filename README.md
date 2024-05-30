<div align="center">
  <h1 align="center">HolmesGPT - The Open Source DevOps Assistant</h1>
<h2 align="center">Solve Problems Twice as Fast with an AI Teammate</h2>
  <p align="center">
    <a href="#use-cases"><strong>Use Cases</strong></a> |
    <a href="#examples"><strong>Examples</strong></a> |
    <a href="#key-features"><strong>Key Features</strong></a> |
    <a href="#installation"><strong>Installation</strong></a> 
  </p>
</div>

The only DevOps assistant that solves problems **like a human does** - by looking at problems and fetching missing data repeatedly until the problem can be solved. Powered by OpenAI or any tool-calling LLM of your choice, including open source models.

### Use Cases:
- **Kubernetes Troubleshooting**: Ask questions about your cloud, identify problems, and troubleshoot them
- **Incident Response**: Investigate firing alerts by gathering data and determining the root cause
- **Ticket Management**: Analyze and resolve tickets related to DevOps tasks
- **Automated Investigation and Triage:** Prioritize critical alerts and resolve the highest impact issues first.
- **Runbook Automation in Plain English:** No more defining runbooks as YAML or complicated workflows. Just describe tasks in plain English and the AI will follow the instructions

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
<summary>Ask Questions About Your Cloud</summary>

```bash
holmes ask "what services does my cluster expose externally?"
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
<summary>Investigate a Jira Ticket</summary>

```bash
holmes investigate jira https://<PLACEDHOLDER>.atlassian.net --jira-username <PLACEHOLDER_EMAIL> --jira-api-key <PLACEHOLDER_API_KEY>
```
</details>

Like what you see? Checkout [more examples](#more-examples) or get started by [installing HolmesGPT](#installation).

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

3. Check that installation was successful:

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

Clone the project from github, and then run:
```
cd holmesgpt
poetry install --no-root
holmes ask "what pods are unhealthy and why?"
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

Add the `api_key` to the config.yaml or pass them via the CLI.
</details>

<details>
<summary>Azure OpenAI</summary>

To work with Azure AI, you need the [Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource). 

```bash
holmes ask "what pods are unhealthy and why?" --llm=azure --api-key=<PLACEHOLDER> --azure-endpoint='<PLACEHOLDER>'
```

</details>

<details>
<summary>Using a self-hosted LLM like llama 3</summary>

You will need an LLM with support for tool-calling. To use it, set the OPENAI_BASE_URL environment variable and run HolmesGPT like usual.
</details>

## More Examples

<details>
<summary>Identify which Helm value to modify</summary>

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

<details>
<summary>Investigate a Prometheus alert and share results in Slack</summary>

By default investigation results are displayed in the CLI itself. You can optionally get these results in a Slack channel:

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093 --destination slack --slack-token <PLACEHOLDER_SLACK_TOKEN> --slack-channel <PLACEHOLDER_SLACK_CHANNEL>
```

Alternatively you can update the `config.yaml` with your Slack details and run: 

```bash
holmes investigate alertmanager --alertmanager-url http://localhost:9093 --destination slack
```

</details>

<details>
<summary>Investigate and update Jira tickets with findings</summary>

By default Jira investigation results are displayed in the CLI itself. But you can use `--update-ticket` to get the results as a comment in the Jira ticket.

```bash
holmes investigate jira https://<PLACEDHOLDER>.atlassian.net --jira-username <PLACEHOLDER_EMAIL> --jira-api-key <PLACEHOLDER_API_KEY> --update-ticket
```

Alternatively you can update the `config.yaml` with your Jira account details and run: 

```bash
holmes investigate jira --update-ticket
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
</details>

## More Integrations

<details>
<summary>Slack</summary>

Adding a Slack integration allows the LLM to send Prometheus Alert investigation details to a Slack channel. To do this you need the following

1. **slack-token**: The Slack API key. You can generate with `pip install robusta-cli && robusta integrations slack`
2. **slack-channel**: The Slack channel where you want to recieve the findings.

Add these values to the `config.yaml` or pass them via the CLI.
</details>

<details>
<summary>Jira</summary>

Adding a Jira integration allows the LLM to fetch Jira tickets and investigate automatically. Optionally it can update the Jira ticked with findings too. You need the following to use this

1. **url**: The URL of your workspace. For example: [https://workspace.atlassian.net](https://workspace.atlassian.net) (**Note:** schema (https) is required)
2. **username**: The email you use to log into your Jira account. Eg: `jira-user@company.com`
3. **api_key**: Follow these [instructions](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/) to get your API key.
4. **project**: Name of the project you want the Jira tickets to be created in. Go to **Project Settings** -> **Details** -> **Name**.
5. **status**: Status of a ticket. Example: `To Do`, `In Progress`

Add these values to the `config.yaml` or pass them via the CLI.
</details>


## License

Distributed under the MIT License. See [LICENSE.txt](https://github.com/robusta-dev/holmesgpt/blob/master/LICENSE.txt) for more information.
<!-- Change License -->

## Support

If you have any questions, feel free to message us on [robustacommunity.slack.com](https://bit.ly/robusta-slack)
