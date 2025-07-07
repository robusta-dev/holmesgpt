# HolmesGPT Evaluations

HolmesGPT uses automated evaluations (evals) to ensure consistent performance across different LLM models and to catch regressions during development. These evaluations test the system's ability to correctly diagnose Kubernetes issues.

- [Writing Evaluations](writing.md) - Learn how to create new test cases and evaluations

## Overview

The eval system comprises two main test suites:

- **Ask Holmes**: Tests single-question interactions with HolmesGPT
- **Investigate**: Tests HolmesGPT's ability to investigate specific issues reported by AlertManager

Evals use fixtures that simulate real Kubernetes environments and tool outputs, allowing comprehensive testing without requiring live clusters.

## Test Status Legend

- ✅ **Successful**: Test passed and meets quality standards
- ⚠️ **Warning**: Test failed but is known to be flaky or expected to fail
- ❌ **Failed**: Test failed and should be fixed before merging

## Why Evaluations Matter

Evaluations serve several critical purposes:

1. **Quality Assurance**: Ensure HolmesGPT provides accurate diagnostics and recommendations
2. **Model Comparison**: Compare performance across different LLM models (GPT-4, Claude, Gemini, etc.)
3. **Regression Testing**: Catch performance degradations when updating code or dependencies
4. **Toolset Validation**: Verify that new toolsets and integrations work correctly
5. **Continuous Improvement**: Identify areas where HolmesGPT needs enhancement

## How to Run Evaluations

### Prerequisites

```bash
poetry install
```

### Basic Usage

Run all evaluations:
```bash
poetry run pytest ./tests/llm/test_*.py --no-cov --disable-warnings
```

By default the tests load and present mock files to the LLM whenever it asks for them. If a mock file is not present for a tool call, the tool call is passed through to the live tool itself. In a lot of cases this can cause the eval to fail unless the live environment (k8s cluster) matches what the LLM expects.

Run specific test suite:
```bash
poetry run pytest ./tests/llm/test_ask_holmes.py --no-cov --disable-warnings
poetry run pytest ./tests/llm/test_investigate.py --no-cov --disable-warnings
```

Run a specific test case:
```bash
poetry run pytest ./tests/llm/test_ask_holmes.py -k "01_how_many_pods" --no-cov --disable-warnings
```

> It is possible to investigate and debug why an eval fails by the output provided in the console. The output includes the correctness score, the reasoning for the score, information about what tools were called, the expected answer, as well as the LLM's answer.

### Environment Variables

Configure evaluations using these environment variables:

| Variable | Example | Description |
|----------|---------|-------------|
| `MODEL` | `MODEL=anthropic/claude-3-5-sonnet-20241022` | Specify which LLM model to use |
| `CLASSIFIER_MODEL` | `CLASSIFIER_MODEL=gpt-4o` | The LLM model to use for scoring the answer (LLM as judge). Defaults to `MODEL` |
| `ITERATIONS` | `ITERATIONS=3` | Run each test multiple times for consistency checking |
| `RUN_LIVE` | `RUN_LIVE=true` | Execute `before-test` and `after-test` commands, ignore mock files |
| `UPLOAD_DATASET` | `UPLOAD_DATASET=true` | Sync dataset to external evaluation platform |
| `EXPERIMENT_ID` | `EXPERIMENT_ID=my_baseline` | Custom experiment name for result tracking |

### Simple Example

Run a comprehensive evaluation:
```bash
export MODEL=gpt-4o

# Run with parallel execution for speed
poetry run pytest -n 10 ./tests/llm/test_*.py --no-cov --disable-warnings
```

### Live Testing

For tests that require actual Kubernetes resources:
```bash
export RUN_LIVE=true

poetry run pytest ./tests/llm/test_ask_holmes.py -k "specific_test" --no-cov --disable-warnings
```

Live testing requires a Kubernetes cluster and will execute `before-test` and `after-test` commands to set up/tear down resources. Not all tests support live testing. Some tests require manual setup.

## Model Comparison Workflow

1. **Create Baseline**: Run evaluations with a reference model
   ```bash
   EXPERIMENT_ID=baseline_gpt4o MODEL=gpt-4o poetry run pytest -n 10 ./tests/llm/test_* --no-cov --disable-warnings
   ```

2. **Test New Model**: Run evaluations with the model you want to compare
   ```bash
   EXPERIMENT_ID=test_claude35 MODEL=anthropic/claude-3-5-sonnet-20241022 poetry run pytest -n 10 ./tests/llm/test_*  --no-cov --disable-warnings
   ```

3. **Compare Results**: Use evaluation tracking tools to analyze performance differences

## Troubleshooting

### Common Issues

1. **Missing API keys**: Some tests are skipped without proper API keys
2. **Live test failures**: Ensure Kubernetes cluster access and proper permissions
3. **Mock file mismatches**: Regenerate mocks with `generate_mocks: true`
4. **Timeout errors**: Increase test timeout or check network connectivity

### Debug Mode

Enable verbose output:
```bash
poetry run pytest -v -s ./tests/llm/test_ask_holmes.py -k "specific_test" --no-cov --disable-warnings
```

This shows detailed output including:
- Expected vs actual results
- Tool calls made by the LLM
- Evaluation scores and rationales
- Debugging information
