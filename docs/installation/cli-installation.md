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
       pipx install holmesgpt
       ```

    3. Verify installation:
       ```bash
       holmes ask --help
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

    3. Verify installation:
       ```bash
       poetry run holmes ask --help
       ```

=== "Docker Container"

    Run HolmesGPT using the prebuilt Docker container:

    ```bash
    docker run -it --net=host \
      -e OPENAI_API_KEY="your-api-key" \
      -v ~/.holmes:/root/.holmes \
      -v ~/.aws:/root/.aws \
      -v ~/.config/gcloud:/root/.config/gcloud \
      -v $HOME/.kube/config:/root/.kube/config \
      us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes ask "what pods are unhealthy and why?"
    ```

    > **Note:** Pass environment variables using `-e` flags. An example for OpenAI is shown above. Adjust it for other AI providers by passing `-e GEMINI_API_KEY`, `-e ANTHROPIC_API_KEY`, etc.

## Quick Start

After installation, choose your AI provider and follow the steps below. See supported [AI Providers](../ai-providers/index.md) for more details.

=== "OpenAI (Default)"

    1. **Set up API key**:
        ```bash
        export OPENAI_API_KEY="your-api-key"
        ```

        See [OpenAI Configuration](../ai-providers/openai.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?"
        ```

=== "Azure OpenAI"

    1. **Set up API key**:
        ```bash
        export AZURE_API_VERSION="2024-02-15-preview"
        export AZURE_API_BASE="https://your-resource.openai.azure.com"
        export AZURE_API_KEY="your-azure-api-key"
        ```

        See [Azure OpenAI Configuration](../ai-providers/azure-openai.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="azure/<your-model-name>"
        ```

=== "AWS Bedrock"

    1. **Set up API key**:
        ```bash
        export AWS_ACCESS_KEY_ID="your-access-key"
        export AWS_SECRET_ACCESS_KEY="your-secret-key"
        export AWS_DEFAULT_REGION="your-region"
        ```

        See [AWS Bedrock Configuration](../ai-providers/aws-bedrock.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="bedrock/<your-model-name>"
        ```

        **Note**: You must install `boto3>=1.28.57` and replace `<your-model-name>` with an actual model name like `anthropic.claude-3-5-sonnet-20240620-v1:0`. See [Finding Available Models](../ai-providers/aws-bedrock.md#finding-available-models) for instructions.

    Ask follow-up questions to refine your investigation

=== "Anthropic Claude"

    1. **Set up API key**:
        ```bash
        export ANTHROPIC_API_KEY="your-api-key"
        ```

        See [Anthropic Configuration](../ai-providers/anthropic.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="anthropic/<your-model-name>"
        ```

=== "Google Gemini"

    1. **Set up API key**:
        ```bash
        export GEMINI_API_KEY="your-gemini-api-key"
        ```

        See [Google Gemini Configuration](../ai-providers/gemini.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="gemini/<your-gemini-model>"
        ```

=== "Google Vertex AI"

    1. **Set up credentials**:
        ```bash
        export VERTEXAI_PROJECT="your-project-id"
        export VERTEXAI_LOCATION="us-central1"
        export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
        ```

        See [Google Vertex AI Configuration](../ai-providers/google-vertex-ai.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="vertex_ai/<your-vertex-model>"
        ```

=== "Ollama"

    1. **Set up API key**:
        No API key required for local Ollama installation.

        See [Ollama Configuration](../ai-providers/ollama.md) for more details.

    2. **Create a test pod** to investigate:
        ```bash
        kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
        ```

    3. **Ask your first question**:
        ```bash
        holmes ask "what is wrong with the user-profile-import pod?" --model="ollama/<your-model-name>"
        ```

    > **Note:** Only LiteLLM supported Ollama models work with HolmesGPT. Check the [LiteLLM Ollama documentation](https://docs.litellm.ai/docs/providers/ollama#ollama-models){:target="_blank"} for supported models.

## Next Steps

- **[Add Data Sources](../data-sources/index.md)** - Use built-in toolsets to connect with ArgoCD, Confluence, and monitoring tools
- **[Connect Remote MCP Servers](../data-sources/remote-mcp-servers.md)** - Extend capabilities with external MCP servers

## Need Help?

- **[Join our Slack](https://bit.ly/robusta-slack){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
