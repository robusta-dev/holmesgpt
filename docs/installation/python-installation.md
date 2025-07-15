# Install Python SDK

Embed HolmesGPT in your own applications with the Python API for programmatic root cause analysis.

## Install HolmesGPT Python Package

```bash
pip install holmesgpt
```

## Quick Start

```python
from holmes.config import Config
from holmes.plugins.prompts import load_and_render_prompt

# Create configuration
config = Config(
    api_key="your-api-key",
    model="gpt-4o",
    max_steps=10
)

# Create AI instance
ai = config.create_console_toolcalling_llm()

# Ask a question
system_prompt = load_and_render_prompt(
    "builtin://generic_ask.jinja2",
    {"toolsets": ai.tool_executor.toolsets}
)

response = ai.prompt_call(system_prompt, "what pods are failing in production?")
print(response.result)
```

## Configuration Options

### Basic Configuration

```python
from holmes.config import Config

# Basic configuration example
config = Config(
    api_key="your-api-key",
    model="gpt-4o",  # or "claude-3-sonnet", "gpt-3.5-turbo", etc.
    max_steps=10
)

# Minimal configuration (API key only)
config = Config(api_key="your-api-key")

# Environment-based configuration
config = Config()  # Will auto-detect API key from OPENAI_API_KEY
```

### Advanced Configuration

```python
from holmes.config import Config

# Complete configuration with custom toolsets and runbooks
config = Config(
    # LLM settings
    api_key="your-api-key",
    model="gpt-4o",
    max_steps=10,

    # Custom toolsets and runbooks
    custom_toolsets=["/path/to/custom/toolset.yaml"],
    custom_runbooks=["/path/to/custom/runbook.yaml"],
)
```

## API Reference

### Config

Main configuration class for HolmesGPT.

**Constructor Parameters:**

- `api_key` (str, optional) - LLM API key (can also use environment variables)
- `model` (str, optional) - Model to use (default: "gpt-4o")
- `max_steps` (int, optional) - Maximum investigation steps (default: 10)
- `custom_toolsets` (list, optional) - Custom toolset file paths
- `custom_runbooks` (list, optional) - Custom runbook file paths

**Class Methods:**

- `Config.load_from_file(path)` - Load configuration from YAML file
- `Config.load_from_env()` - Load configuration from environment variables

**Instance Methods:**

- `create_console_toolcalling_llm()` - Create AI instance for investigations

### ToolCallingLLM

Main AI instance for running investigations.

**Methods:**

- `prompt_call(system_prompt, user_prompt)` - Ask a question and get response
- `call(messages)` - Call with full message history

## Environment Variables

Instead of passing `api_key` to the Config constructor, you can set these environment variables and use `Config()` without parameters:

```bash
# AI Provider (choose one)
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export GOOGLE_API_KEY="your-google-key"

# Optional: Custom configuration
export HOLMES_CONFIG_PATH="/path/to/config.yaml"
export HOLMES_LOG_LEVEL="INFO"
```

**Usage with environment variables:**
```python
import os
os.environ["OPENAI_API_KEY"] = "your-api-key"

config = Config()  # Will auto-detect API key from environment
```

## Need Help?

- **[Join our Slack](https://robustacommunity.slack.com){:target="_blank"}** - Get help from the community
- **[Request features on GitHub](https://github.com/robusta-dev/holmesgpt/issues){:target="_blank"}** - Suggest improvements or report bugs
- **[Troubleshooting guide](../reference/troubleshooting.md)** - Common issues and solutions
