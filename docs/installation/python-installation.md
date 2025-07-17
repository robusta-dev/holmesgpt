# Install Python SDK

Embed HolmesGPT in your own applications for programmatic root cause analysis, based on observability data.

## Install HolmesGPT Python Package

```bash
pip install "https://github.com/robusta-dev/holmesgpt/archive/refs/heads/master.zip"
```

## Quick Start

```python
import os
from holmes.config import Config
from holmes.plugins.prompts import load_and_render_prompt

print("🚀 Initializing HolmesGPT...")

# Create configuration
print("Creating configuration...")
config = Config(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o",
    max_steps=10
)
print(f"✅ Configuration created with model: {config.model}")

# Create AI instance
print("Creating AI instance...")
ai = config.create_console_toolcalling_llm()
print("✅ AI instance ready")

# Ask a question
print("Loading system prompt...")
system_prompt = load_and_render_prompt(
    "builtin://generic_ask.jinja2",
    {"toolsets": ai.tool_executor.toolsets}
)
print("✅ System prompt loaded")

print("\n🔍 Asking: 'what pods are failing in production?'")
print("Holmes is thinking...")
response = ai.prompt_call(system_prompt, "what pods are failing in production?")
print(f"Holmes: {response.result}")
```

## Tool Details Example

Here's a complete working example that shows detailed progress, available tools, toolsets, and which tools Holmes uses:

```python
#!/usr/bin/env python3
"""
Complete example of using HolmesGPT Python SDK with progress tracking
"""

import os
from holmes.config import Config
from holmes.plugins.prompts import load_and_render_prompt

def main():
    print("🚀 Starting HolmesGPT Python SDK Example")
    print("=" * 60)

    # Set API key (you can also set OPENAI_API_KEY environment variable)
    api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")

    print("Step 1: Creating configuration...")
    # Create configuration
    config = Config(
        api_key=api_key,
        model="gpt-4o",
        max_steps=10
    )
    print(f"✅ Configuration created with model: {config.model}")

    print("\nStep 2: Creating AI instance...")
    # Create AI instance
    ai = config.create_console_toolcalling_llm()
    print("✅ AI instance created successfully")

    print("\nStep 3: Listing available toolsets...")
    # Show available toolsets
    toolsets = ai.tool_executor.toolsets
    print(f"Loaded {len(toolsets)} toolsets:")
    for toolset in toolsets:
        print(f"   • {toolset.name} ({'enabled' if toolset.enabled else 'disabled'})")

    print("\nStep 4: Listing available tools from loaded toolsets...")
    # Show available tools
    available_tools = list(ai.tool_executor.tools_by_name.keys())
    print(f"Listed {len(available_tools)} tools:")
    for tool in sorted(available_tools):
        print(f"   • {tool}")

    print("\nStep 5: Loading system prompt...")
    # Load system prompt
    system_prompt = load_and_render_prompt(
        "builtin://generic_ask.jinja2",
        {"toolsets": ai.tool_executor.toolsets}
    )
    print("✅ System prompt loaded successfully")
    print(f"Prompt length: {len(system_prompt)} characters")

    print("\nStep 6: Asking questions...")
    # Ask questions
    questions = [
        "what pods are failing in production?",
        "show me recent kubernetes events",
        "what are the resource usage patterns in my cluster?"
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Question {i}/{len(questions)}: {question}")
        print("=" * 60)

        try:
            print("Holmes is thinking...")
            response = ai.prompt_call(system_prompt, question)
            print(f"Holmes: {response.result}")

            # Show tools that were used
            if response and response.tool_calls:
                tool_names = [tool.tool_name for tool in response.tool_calls]
                if tool_names:
                    print(f"\nTools used: {tool_names}")

                    # Print contents of each tool response
                    print("\nTool responses:")
                    for j, tool in enumerate(response.tool_calls, 1):
                        print(f"\n   {j}. {tool.tool_name}:")
                        print(f"      Result: {tool.result}")
                        if hasattr(tool, 'error') and tool.error:
                            print(f"      Error: {tool.error}")

        except Exception as e:
            print(f"❌ Error: {e}")

        print("-" * 60)

    print("\n✅ Example completed!")

if __name__ == "__main__":
    main()
```

Save this as `holmesgpt_tool_details_example.py` and run:

```bash
# Make sure your API key is set
export OPENAI_API_KEY="your-actual-api-key"

# Run the example
python holmesgpt_tool_details_example.py
```

This will show you:

- Configuration creation progress
- List of available tools (kubectl, prometheus, etc.)
- List of available toolsets and their status
- System prompt loading progress
- Progress for each question being asked
- Which tools Holmes used for each question

## Follow-up Questions Example

Here's how to ask follow-up questions that maintain conversation context:

```python
#!/usr/bin/env python3
"""
Example showing how to ask follow-up questions with conversation context
"""

import os
from holmes.config import Config
from holmes.plugins.prompts import load_and_render_prompt
from holmes.core.prompt import build_initial_ask_messages
from rich.console import Console

def main():
    print("🚀 Starting HolmesGPT Follow-up Questions Example")
    print("=" * 60)

    # Create configuration
    config = Config(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o",
        max_steps=10
    )

    # Create AI instance and console
    ai = config.create_console_toolcalling_llm()
    console = Console()

    # Load system prompt
    system_prompt = load_and_render_prompt(
        "builtin://generic_ask.jinja2",
        {"toolsets": ai.tool_executor.toolsets}
    )

    # First question
    print("\n🔍 First Question:")
    first_question = "what pods are failing in my cluster?"
    print(f"User: {first_question}")

    # Build initial messages (system + first user message)
    messages = build_initial_ask_messages(
        console, system_prompt, first_question, None
    )

    # Call AI with initial messages
    print("Holmes is thinking...")
    response = ai.call(messages)
    messages = response.messages  # Update messages with full conversation

    print(f"Holmes: {response.result}")

    # Follow-up question
    followup_question = "Can you show me the logs for those failing pods?"

    print(f"\n🔍 Follow-up Question:")
    print(f"User: {followup_question}")

    # Add the follow-up question to the conversation
    messages.append({"role": "user", "content": followup_question})

    # Call AI with updated message history
    print("Holmes is thinking...")
    response = ai.call(messages)
    messages = response.messages  # Update messages with latest response

    print(f"Holmes: {response.result}")

    # Show tools used
    if response.tool_calls:
        tool_names = [tool.tool_name for tool in response.tool_calls]
        print(f"Tools used: {tool_names}")

    print("\n✅ Conversation completed!")
    print(f"Total messages in conversation: {len(messages)}")

if __name__ == "__main__":
    main()
```

**Key Points for Follow-up Questions:**

1. **Use `build_initial_ask_messages()`** for the first question
2. **Use `ai.call(messages)`** instead of `ai.prompt_call()`
3. **Update messages after each response**: `messages = response.messages`
4. **Append new questions**: `messages.append({"role": "user", "content": question})`
5. **Messages contain full conversation history** for context

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
