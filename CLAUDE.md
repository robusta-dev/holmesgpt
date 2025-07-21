# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

HolmesGPT is an AI-powered troubleshooting agent that connects to observability platforms (Kubernetes, Prometheus, Grafana, etc.) to automatically diagnose and analyze infrastructure and application issues. It uses an agentic loop to investigate problems by calling tools to gather data from multiple sources.

## Development Commands

### Environment Setup
```bash
# Install dependencies with Poetry
poetry install

# Install pre-commit hooks
poetry run pre-commit install
```

### Testing
```bash
# Run all non-LLM tests (unit and integration tests)
make test-without-llm
poetry run pytest tests -m "not llm"

# Run LLM evaluation tests (requires API keys)
make test-llm-ask-holmes          # Test single-question interactions
make test-llm-investigate         # Test AlertManager investigations
poetry run pytest tests/llm/ -n 6 -vv  # Run all LLM tests in parallel

# Run pre-commit checks (includes ruff, mypy, poetry validation)
make check
poetry run pre-commit run -a
```

### Code Quality
```bash
# Format code with ruff
poetry run ruff format

# Check code with ruff (auto-fix issues)
poetry run ruff check --fix

# Type checking with mypy
poetry run mypy
```

## Architecture Overview

### Core Components

**CLI Entry Point** (`holmes/main.py`):
- Typer-based CLI with subcommands for `ask`, `investigate`, `toolset`
- Handles configuration loading, logging setup, and command routing

** Interactive mode for CLI** (`holmes/interactive.py`):
- Handles interactive mode for `ask` subcommand
- Implements slash commands

**Configuration System** (`holmes/config.py`):
- Loads settings from `~/.holmes/config.yaml` or via CLI options
- Manages API keys, model selection, and toolset configurations
- Factory methods for creating sources (AlertManager, Jira, PagerDuty, etc.)

**Core Investigation Engine** (`holmes/core/`):
- `tool_calling_llm.py`: Main LLM interaction with tool calling capabilities
- `investigation.py`: Orchestrates multi-step investigations with runbooks
- `toolset_manager.py`: Manages available tools and their configurations
- `tools.py`: Tool definitions and execution logic

**Plugin System** (`holmes/plugins/`):
- **Sources**: AlertManager, Jira, PagerDuty, OpsGenie integrations
- **Toolsets**: Kubernetes, Prometheus, Grafana, AWS, Docker, etc.
- **Prompts**: Jinja2 templates for different investigation scenarios
- **Destinations**: Slack integration for sending results

### Key Patterns

**Toolset Architecture**:
- Each toolset is a YAML file defining available tools and their parameters
- Tools can be Python functions or bash commands with safety validation
- Toolsets are loaded dynamically and can be customized via config files

**LLM Integration**:
- Uses LiteLLM for multi-provider support (OpenAI, Anthropic, Azure, etc.)
- Structured tool calling with automatic retry and error handling
- Context-aware prompting with system instructions and examples

**Investigation Flow**:
1. Load user question/alert
2. Select relevant toolsets based on context
3. Execute LLM with available tools
4. LLM calls tools to gather data
5. LLM analyzes results and provides conclusions
6. Optionally write results back to source system

## Testing Framework

**Three-tier testing approach**:

1. **Unit Tests** (`tests/`): Standard pytest tests for individual components
2. **Integration Tests**: Test toolset integrations with mock responses
3. **LLM Evaluation Tests** (`tests/llm/`): End-to-end tests using fixtures

**LLM Test Structure**:
- `tests/llm/fixtures/test_ask_holmes/`: 53+ test scenarios with YAML configs
- Each test has mock tool responses and expected outputs
- Uses LLM-as-judge for automated evaluation
- Supports Braintrust integration for result tracking

**Running LLM Tests**:
```bash
# Test specific scenario
poetry run pytest tests/llm/test_ask_holmes.py -k "01_how_many_pods"

# Use live tools instead of mocks
export RUN_LIVE=true
poetry run pytest tests/llm/test_ask_holmes.py

# Test with different models
export MODEL=anthropic/claude-3.5
poetry run pytest tests/llm/test_ask_holmes.py
```

## Configuration

**Config File Location**: `~/.holmes/config.yaml`

**Key Configuration Sections**:
- `model`: LLM model to use (default: gpt-4o)
- `api_key`: LLM API key (or use environment variables)
- `custom_toolsets`: Override or add toolsets
- `custom_runbooks`: Add investigation runbooks
- Platform-specific settings (alertmanager_url, jira_url, etc.)

**Environment Variables**:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`: LLM API keys
- `MODEL`: Override default model
- `RUN_LIVE`: Use live tools in tests instead of mocks
- `BRAINTRUST_API_KEY`: For test result tracking

## Development Guidelines

**Code Quality**:
- Use Ruff for formatting and linting (configured in pyproject.toml)
- Type hints required (mypy configuration in pyproject.toml)
- Pre-commit hooks enforce quality checks

**Testing Requirements**:
- All new features require unit tests
- New toolsets require integration tests with mocks
- Complex investigations should have LLM evaluation tests
- Maintain 40% minimum test coverage

**Pull Request Process**:
- PRs require maintainer approval
- Pre-commit hooks must pass
- LLM evaluation tests run automatically in CI
- Keep PRs focused and include tests

**File Structure Conventions**:
- Toolsets: `holmes/plugins/toolsets/{name}.yaml` or `{name}/`
- Prompts: `holmes/plugins/prompts/{name}.jinja2`
- Tests: Match source structure under `tests/`
- Mock data: `tests/llm/fixtures/{test_name}/`

## Security Notes

- All tools have read-only access by design
- Bash toolset validates commands for safety
- No secrets should be committed to repository
- Use environment variables or config files for API keys
- RBAC permissions are respected for Kubernetes access
