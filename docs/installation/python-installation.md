# Install Python SDK

Embed HolmesGPT in your own applications with the Python API for programmatic root cause analysis.

## Install Robusta Python SDK

```bash
pip install robusta
```

## Quick Start

```python
from holmes import ask_holmes

# Ask a simple question
result = ask_holmes("what pods are failing in production?")
print(result)

# Analyze with additional context files
result = ask_holmes(
    "analyze this pod failure",
    context_files=["pod.yaml", "logs.txt"]
)
print(result)
```

## API Reference

### Core Functions

#### `ask_holmes(question, **kwargs)`

Ask Holmes a question synchronously.

**Parameters:**
- `question` (str): The question to ask
- `context_files` (list, optional): List of file paths for context
- `toolsets` (list, optional): Custom toolsets to use
- `config` (Config, optional): Custom configuration

**Returns:**
- `str`: Holmes' analysis and recommendations

#### `ask_holmes_async(question, **kwargs)`

Async version of `ask_holmes()`.

#### `HolmesGPT(config=None)`

Main Holmes class for advanced usage.

**Methods:**
- `investigate(question)`: Run investigation
- `add_toolset(toolset)`: Add custom toolset
- `set_context(context)`: Set investigation context

### Configuration Options

```python
from holmes.config import Config

config = Config(
    # AI Provider settings
    ai_provider="openai",  # "openai", "anthropic", "bedrock", "vertex"
    api_key="your-key",
    model="gpt-4",

    # Investigation settings
    max_tokens=2000,
    temperature=0.1,
    enable_context=True,

    # Kubernetes settings
    kubeconfig_path="~/.kube/config",
    default_namespace="default",

    # Custom toolsets
    custom_toolsets=[],
    enabled_toolsets=["kubernetes", "prometheus"]
)
```

## Environment Variables

Set these environment variables for configuration:

```bash
# AI Provider (choose one)
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export GOOGLE_API_KEY="your-google-key"

# Optional: Custom configuration
export HOLMES_CONFIG_PATH="/path/to/config.yaml"
export HOLMES_LOG_LEVEL="INFO"
```

## Need Help?

- **[Join our Slack](https://robustacommunity.slack.com){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
