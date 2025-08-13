# HolmesGPT Evaluations

Evaluations are automated tests that measure HolmesGPT's accuracy on real-world scenarios.

They are used to both catch regressions and measure the impact of new features.

[Example: pod crashloop eval](https://github.com/robusta-dev/holmesgpt/tree/master/tests/llm/fixtures/test_ask_holmes/09_crashpod).

## Eval Tags

Evals are tagged and grouped into categories. Two common tags are `easy` and `medium`:

* `easy` - regression tests - scenarios that HolmesGPT passes today and must continue to pass after any change
* `medium` - more challenging scenarios that push boundaries of what HolmesGPT can do

Changes to HolmesGPT are good if they allow us to promote an eval from `easy` to `medium` without increasing latency by too much.

## Getting Started

### Prerequisites

Install HolmesGPT python dependencies:

```bash
poetry install --with=dev
```

### Basic Commands

```bash
# Run all easy evals - these should always pass assuming you have a kubernetes cluster with sufficient resources and a 'good enough model' (e.g. gpt-4o)
RUN_LIVE=true poetry run pytest -m 'llm and easy' --no-cov

# Run a specific eval
RUN_LIVE=true poetry run pytest tests/llm/test_ask_holmes.py -k "01_how_many_pods"

# Run evals with a specific tag
RUN_LIVE=true poetry run pytest -m "llm and logs" --no-cov
```

### Testing Different Models

The `MODEL` environment variable is equivalent to the `--model` flag on the `holmes ask` CLI command. You can test HolmesGPT with different LLM providers:

```bash
# Test with GPT-4 (default)
RUN_LIVE=true MODEL=gpt-4o poetry run pytest -m 'llm and easy'

# Test with Claude
# Note: CLASSIFIER_MODEL must be set to OpenAI or Azure as Anthropic models are not currently supported for classification
RUN_LIVE=true MODEL=anthropic/claude-3-5-sonnet-20241022 CLASSIFIER_MODEL=gpt-4o poetry run pytest -m 'llm and easy'

# Test with Azure OpenAI
# Set required Azure environment variables for your deployment
export AZURE_API_KEY=your-azure-api-key
export AZURE_API_BASE=https://your-deployment.openai.azure.com/
export AZURE_API_VERSION=2024-02-15-preview
RUN_LIVE=true MODEL=azure/your-deployment-name CLASSIFIER_MODEL=azure/your-deployment-name poetry run pytest -m 'llm and easy'
```

**Important Notes:**

- When using Anthropic models, you must set `CLASSIFIER_MODEL` to an OpenAI or Azure model because the evaluation framework's classifier currently only supports these providers
- For any model provider, ensure you have the necessary API keys and environment variables set (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AZURE_API_KEY`)
- The model specified here is passed directly to LiteLLM, so any model supported by LiteLLM can be used

### Running Evals with Multiple Iterations

LLMs are non-deterministic - they produce different outputs for the same input. **10 iterations is a good rule of thumb** for reliable results.

```bash
# Recommended: Run with multiple iterations
RUN_LIVE=true ITERATIONS=10 poetry run pytest -m 'llm and easy' --no-cov

# Quick check: Single run (less reliable)
RUN_LIVE=true poetry run pytest -m 'llm and easy' --no-cov
```

### Using RUN_LIVE=true vs Mock Data

Some evals support mock-data and don't need a live Kubernetes cluster to run. However, for the most accurate evaluation you should set `RUN_LIVE=true` which tests HolmesGPT with a live Kubernetes cluster not mock data.

This is important because LLMs can take multiple paths to reach conclusions, and mock data only captures one path. See [Using Mock Data](../../using-mock-data.md) for rare cases when mocks are necessary.

## Environment Variables

Essential variables for controlling test behavior:

| Variable | Purpose | Example |
|----------|---------|---------|
| `RUN_LIVE` | Use real tools instead of mocks | `RUN_LIVE=true` |
| `ITERATIONS` | Run each test N times | `ITERATIONS=10` |
| `MODEL` | LLM to test | `MODEL=gpt-4o` |
| `CLASSIFIER_MODEL` | LLM for scoring (needed for Anthropic) | `CLASSIFIER_MODEL=gpt-4o` |
| `ASK_HOLMES_TEST_TYPE` | Message building flow (`cli` or `server`) | `ASK_HOLMES_TEST_TYPE=server` |

### ASK_HOLMES_TEST_TYPE Details

The `ASK_HOLMES_TEST_TYPE` environment variable controls how messages are built in ask_holmes tests:

- **`cli` (default)**: Uses `build_initial_ask_messages` like the CLI ask() command. This mode:
  - Simulates the CLI interface behavior
  - Does not support conversation history tests (will skip them)
  - Includes runbook loading and system prompts as done in the CLI

- **`server`**: Uses `build_chat_messages` with ChatRequest for server-style flow. This mode:
  - Simulates the API/server interface behavior
  - Supports conversation history tests
  - Uses the ChatRequest model for message building

```bash
# Test with CLI-style message building (default)
RUN_LIVE=true poetry run pytest -k "test_name"

# Test with server-style message building
RUN_LIVE=true ASK_HOLMES_TEST_TYPE=server poetry run pytest -k "test_name"
```

## Advanced Usage

### Parallel Execution

Speed up test runs with parallel workers:

```bash
# Run with 10 parallel workers
RUN_LIVE=true ITERATIONS=10 poetry run pytest tests/llm/ -n 10
```

### Debugging Failed Tests

When tests fail, use these techniques to investigate:

```bash
# 1. Verbose output to see details
RUN_LIVE=true pytest -vv -s tests/llm/test_ask_holmes.py -k "failing_test"

# 2. Keep resources after test for inspection
RUN_LIVE=true pytest -k "test" --skip-cleanup

# 3. Iterate quickly without setup/cleanup
RUN_LIVE=true pytest -k "test" --skip-setup --skip-cleanup

# 4. Clean up when done debugging
RUN_LIVE=true pytest -k "test" --skip-setup
```

## Model Comparison Workflow

Track performance across different models:

```bash
# 1. Baseline with GPT-4
RUN_LIVE=true ITERATIONS=10 EXPERIMENT_ID=baseline_gpt4o MODEL=gpt-4o pytest -n 10 tests/llm/

# 2. Compare with Claude
RUN_LIVE=true ITERATIONS=10 EXPERIMENT_ID=claude35 MODEL=anthropic/claude-3-5-sonnet CLASSIFIER_MODEL=gpt-4o pytest -n 10 tests/llm/

# 3. Results will be tracked if BRAINTRUST_API_KEY is set
export BRAINTRUST_API_KEY=your-key
```

## Test Markers

Filter tests by functionality:

```bash
# Regression tests (should always pass)
RUN_LIVE=true ITERATIONS=10 poetry run pytest -m "llm and easy"

# Challenging tests
RUN_LIVE=true ITERATIONS=10 poetry run pytest -m "llm and medium"

# Tests involving logs
RUN_LIVE=true poetry run pytest -m "llm and logs"
```

See `pyproject.toml` for all available markers.
