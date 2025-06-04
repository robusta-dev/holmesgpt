# AI Providers

HolmesGPT supports multiple AI providers, giving you flexibility in choosing the best model for your needs and budget.

## Supported Providers

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **Anthropic**

    ---

    Claude models with excellent reasoning capabilities for complex troubleshooting.

    [:octicons-arrow-right-24: Configuration](anthropic.md)

-   :material-aws:{ .lg .middle } **AWS Bedrock**

    ---

    AWS managed AI service with support for multiple model providers.

    [:octicons-arrow-right-24: Configuration](aws-bedrock.md)

-   :material-microsoft-azure:{ .lg .middle } **Azure OpenAI**

    ---

    Enterprise-grade OpenAI through Microsoft Azure with enhanced security.

    [:octicons-arrow-right-24: Configuration](azure-openai.md)

-   :material-google:{ .lg .middle } **Gemini**

    ---

    Google's Gemini models via Google AI Studio for direct API access.

    [:octicons-arrow-right-24: Configuration](gemini.md)

-   :material-google-cloud:{ .lg .middle } **Google Vertex AI**

    ---

    Enterprise Google Cloud AI with Gemini models and advanced features.

    [:octicons-arrow-right-24: Configuration](google-vertex-ai.md)

-   :material-llama:{ .lg .middle } **Ollama**

    ---

    Run large language models locally on your machine for privacy and offline use.

    [:octicons-arrow-right-24: Configuration](ollama.md)

-   :material-openai:{ .lg .middle } **OpenAI**

    ---

    Direct access to GPT-4o and other cutting-edge OpenAI models.

    [:octicons-arrow-right-24: Configuration](openai.md)

-   :material-api:{ .lg .middle } **OpenAI-Compatible**

    ---

    Any OpenAI-compatible API or self-hosted inference server.

    [:octicons-arrow-right-24: Configuration](openai-compatible.md)

</div>

## Quick Start

!!! tip "Recommended for New Users"
    **OpenAI GPT-4o** provides the best balance of accuracy and reliability. Get started with:

    1. Get an [OpenAI API key](https://platform.openai.com/api-keys)
    2. Set `export OPENAI_API_KEY="your-api-key"`
    3. Run `holmes ask "what pods are failing?"`

Choose your provider above to see detailed configuration instructions.
