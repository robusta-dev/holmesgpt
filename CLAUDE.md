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
export MODEL=anthropic/claude-3.5-sonnet-20241022
poetry run pytest tests/llm/test_ask_holmes.py
```

### Evaluation CLI Reference

**Custom Pytest Flags**:
- `--generate-mocks`: Generate mock data files during test execution
- `--regenerate-all-mocks`: Regenerate all mock files (implies --generate-mocks)
- `--skip-setup`: Skip before_test commands (useful for iterative testing)
- `--skip-cleanup`: Skip after_test commands (useful for debugging)

**Environment Variables**:
- `MODEL`: LLM model to use (e.g., `gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`)
- `CLASSIFIER_MODEL`: Model for scoring answers (defaults to MODEL)
- `RUN_LIVE=true`: Execute real commands instead of using mocks
- `ITERATIONS=<number>`: Run each test multiple times
- `UPLOAD_DATASET=true`: Sync dataset to Braintrust
- `EXPERIMENT_ID`: Custom experiment name for tracking
- `BRAINTRUST_API_KEY`: Enable Braintrust integration

**Common Evaluation Patterns**:

```bash

# Generate/update mocks for specific tests
poetry run pytest tests/llm/test_ask_holmes.py -k "test_name" --generate-mocks

# Run tests multiple times for reliability
ITERATIONS=100 poetry run pytest tests/llm/test_ask_holmes.py -k "flaky_test"

# Model comparison workflow
EXPERIMENT_ID=gpt4o_baseline MODEL=gpt-4o poetry run pytest tests/llm/ -n 6
EXPERIMENT_ID=claude35_test MODEL=anthropic/claude-3-5-sonnet-20241022 poetry run pytest tests/llm/ -n 6

# Debug with verbose output
poetry run pytest -vv -s tests/llm/test_ask_holmes.py -k "failing_test" --no-cov

# List tests by marker
poetry run pytest -m "llm and not network" --collect-only -q
```

**Available Test Markers**:
- `llm`: LLM behavior tests
- `datetime`: Datetime functionality
- `logs`: Log processing
- `context_window`: Context window handling
- `synthetic`: Synthetic data tests
- `network`: Network-dependent tests
- `runbooks`: Runbook functionality
- `misleading-history`: Misleading data scenarios
- `k8s-misconfig`: Kubernetes misconfigurations
- `chain-of-causation`: Causation analysis
- `slackbot`: Slack integration
- `counting`: Resource counting tests

**Test Infrastructure Notes**:
- All test state tracking uses pytest's `user_properties` to ensure compatibility with pytest-xdist parallel execution
- Mock file tracking and test results are stored in `user_properties` and aggregated in the terminal summary
- This design ensures tests work correctly when run in parallel with `-n` flag
- **Important for LLM tests**: Each test must use a dedicated namespace `app-<testid>` (e.g., `app-01`, `app-02`) to prevent conflicts when tests run simultaneously
- All pod names must be unique across tests (e.g., `giant-narwhal`, `blue-whale`, `sea-turtle`) - never reuse pod names between tests
- **Resource naming in evals**: Never use names that hint at the problem or expected behavior (e.g., avoid `broken-pod`, `test-project-that-does-not-exist`, `crashloop-app`). Use neutral names that don't give away what the LLM should discover

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
- `BRAINTRUST_API_KEY`: For test result tracking and CI/CD report generation
- `BRAINTRUST_ORG`: Braintrust organization name (default: "robustadev")

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
