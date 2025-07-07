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

    3. Verify installation:
       ```bash
       holmes --help
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

After installation, set up your AI provider and run your first investigation:

1. **Set up API key** (see [supported AI providers](../ai-providers/index.md)):
   ```bash
   export OPENAI_API_KEY="your-api-key"
   export ANTHROPIC_API_KEY="your-api-key"
   export GOOGLE_API_KEY="your-api-key"
   ```

2. **Create a test pod** to investigate:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
   ```

3. **Ask your first question**:
   ```bash
   holmes ask "what is wrong with the user-profile-import pod?"
   ```

4. **Try interactive mode**:
   ```bash
   holmes ask "what pods are unhealthy and why?" --interactive
   ```


## Need Help?

- Check our [troubleshooting guide](../reference/troubleshooting.md)
- Join our [Slack community](https://robustacommunity.slack.com){:target="_blank"}
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}
