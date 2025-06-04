# Install Python SDK

Embed HolmesGPT in your own applications with the Python API for programmatic root cause analysis.

## Installation

### Using pip

```bash
pip install holmesgpt
```

### Using pipenv

```bash
pipenv install holmesgpt
```

### Using poetry

```bash
poetry add holmesgpt
```

## Quick Start

### Basic Usage

```python
from holmes import ask_holmes

# Simple question
result = ask_holmes("what pods are failing in production?")
print(result)

# With specific context
result = ask_holmes(
    "analyze this pod failure",
    context_files=["pod.yaml", "logs.txt"]
)
print(result)
```

### Advanced Configuration

```python
from holmes.core import HolmesGPT
from holmes.config import Config

# Configure with custom settings
config = Config(
    ai_provider="openai",
    api_key="your-api-key",
    model="gpt-4",
    max_tokens=2000
)

# Initialize Holmes
holmes = HolmesGPT(config)

# Run investigation
result = holmes.investigate("what's wrong with my deployment?")
```

### Async Support

```python
import asyncio
from holmes import ask_holmes_async

async def investigate_issue():
    result = await ask_holmes_async("check cluster health")
    return result

# Run async investigation
result = asyncio.run(investigate_issue())
```

## Use Cases

### CI/CD Integration

```python
import os
from holmes import ask_holmes

def check_deployment_health(namespace):
    """Check if deployment was successful"""
    question = f"are all pods healthy in {namespace} namespace?"
    result = ask_holmes(question)

    if "unhealthy" in result.lower():
        print(f"❌ Deployment issues found: {result}")
        return False
    else:
        print(f"✅ Deployment successful: {result}")
        return True

# Use in CI/CD pipeline
if not check_deployment_health("production"):
    os.exit(1)
```

### Monitoring Integration

```python
from holmes import ask_holmes
import time

def monitor_cluster():
    """Continuous cluster monitoring"""
    while True:
        try:
            result = ask_holmes("what issues need attention?")
            if "critical" in result.lower():
                send_alert(result)
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Monitoring error: {e}")

def send_alert(message):
    # Integration with your alerting system
    print(f"🚨 ALERT: {message}")
```

### Custom Toolsets

```python
from holmes.core import HolmesGPT
from holmes.toolsets import CustomToolset

# Define custom toolset
class MyCustomToolset(CustomToolset):
    def get_custom_data(self):
        # Your custom data collection logic
        return {"custom_metrics": "data"}

# Configure Holmes with custom toolset
holmes = HolmesGPT()
holmes.add_toolset(MyCustomToolset())

result = holmes.investigate("analyze using my custom data")
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

## Examples Repository

Check out our [examples repository](https://github.com/robusta-dev/holmesgpt-examples) for:

- **Flask integration** - Web app with Holmes
- **Slack bot** - Custom Slack integration
- **Jupyter notebooks** - Data analysis workflows
- **CI/CD pipelines** - GitHub Actions examples

## Next Steps

- **[API Keys Setup](../api-keys.md)** - Configure your AI provider
- **[Run Your First Investigation](first-investigation.md)** - Complete walkthrough
- **[Helm Configuration](../reference/helm-configuration.md)** - Advanced settings and custom toolsets

## Need Help?

- Check our [Python SDK documentation](../python.md) for detailed API reference
- Join our [Slack community](https://robustacommunity.slack.com)
- Report issues on [GitHub](https://github.com/robusta-dev/holmesgpt/issues)
