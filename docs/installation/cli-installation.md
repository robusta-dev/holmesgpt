# Install CLI

Run HolmesGPT from your terminal as a standalone CLI tool.

## Installation Options

=== "Homebrew (Mac/Linux)"

    1. Add our tap:
       ```bash
       brew tap robusta-dev/homebrew-holmesgpt
       ```

    2. Install HolmesGPT:
       ```bash
       brew install holmesgpt
       ```

    3. To upgrade to the latest version:
       ```bash
       brew upgrade holmesgpt
       ```

    4. Verify installation:
       ```bash
       holmes ask --help
       ```

=== "Pipx"

    1. Install [pipx](https://pypa.github.io/pipx/installation/){:target="_blank"}

    2. Install HolmesGPT:
       ```bash
       pipx install "https://github.com/robusta-dev/holmesgpt/archive/refs/heads/master.zip"
       ```

    3. Verify installation:
       ```bash
       holmes version
       ```

=== "From Source (Poetry)"

    For development or custom builds:

    1. Install [Poetry](https://python-poetry.org/docs/#installation){:target="_blank"}

    2. Install HolmesGPT:
       ```bash
       git clone https://github.com/robusta-dev/holmesgpt.git
       cd holmesgpt
       poetry install --no-root
       ```

    3. Run HolmesGPT:
       ```bash
       poetry run python3 holmes_cli.py ask "what pods are unhealthy and why?"
       ```

=== "Docker Container"

    Run HolmesGPT using the prebuilt Docker container:

    ```bash
    docker run -it --net=host \
      -v ~/.holmes:/root/.holmes \
      -v ~/.aws:/root/.aws \
      -v ~/.config/gcloud:/root/.config/gcloud \
      -v $HOME/.kube/config:/root/.kube/config \
      us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes ask "what pods are unhealthy and why?"
    ```

## Quick Start

After installation, set up your [AI provider](../ai-providers/index.md) and run your first investigation:

1. **Set up API key**:
```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Azure OpenAI
export AZURE_API_VERSION="2024-02-15-preview"
export AZURE_API_BASE="https://your-resource.openai.azure.com/"
export AZURE_API_KEY="your-azure-api-key"

# Google
export GOOGLE_API_KEY="your-api-key"
```
See supported [AI Providers](../ai-providers/index.md) for more details.

2. **Create a test pod** to investigate:
```bash
kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
```

3. **Ask your first question**:

    === "OpenAI (Default)"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?"
        ```

    === "Azure OpenAI"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="azure/<your-model-name>"
        ```

    === "Anthropic Claude"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="anthropic/<your-model-name>"
        ```

    === "Google Gemini"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="google/<your-model-name>"
        ```

    === "AWS Bedrock"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="bedrock/<your-model-name>"
        ```

    === "Ollama"
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="ollama/<your-model-name>"
        ```

    Ask follow-up questions to refine your investigation

## Next Steps

- **[AI Provider Setup](ai-providers/index.md)** - Configure your AI provider
- **[Run Your First Investigation](../walkthrough/index.md)** - Complete walkthrough with examples
- **[Add integrations](data-sources/index.md)** - Connect monitoring tools like Prometheus and Grafana
- **[Troubleshooting guide](reference/troubleshooting.md)** - Common issues and solutions

## Need Help?

- **[Join our Slack](https://robustacommunity.slack.com){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
