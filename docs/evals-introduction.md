# HolmesGPT Evaluations - Introduction

## Executive Summary

HolmesGPT uses automated evaluations (evals) to ensure consistent performance across different LLM models and to catch regressions during development. These evaluations test the system's ability to correctly diagnose Kubernetes issues.

The eval system comprises two main test suites:

- **Ask Holmes**: Tests single-question interactions with HolmesGPT
- **Investigate**: Tests HolmesGPT's ability to investigate specific issues reported by AlertManager

Evals use fixtures that simulate real Kubernetes environments and tool outputs, allowing comprehensive testing without requiring live clusters. 

While results are tracked and analyzed using Braintrust, Braintrust is not necessary to writing, running and debugging evals.

## Why Evaluations Matter

Evaluations serve several critical purposes:

1. **Quality Assurance**: Ensure HolmesGPT provides accurate diagnostics and recommendations
2. **Model Comparison**: Compare performance across different LLM models (GPT-4, Claude, Gemini, etc.)
3. **Regression Testing**: Catch performance degradations when updating code or dependencies
4. **Toolset Validation**: Verify that new toolsets and integrations work correctly
5. **Continuous Improvement**: Identify areas where HolmesGPT needs enhancement

## How to Run Evaluations

### Basic Usage

Run all evaluations:
```bash
pytest ./tests/llm/test_*.py
```

By default the tests load and present mock files to the LLM whenever it asks for them. If a mock file is not present for a tool call, the tool call is passed through to the live tool itself. In a lot of cases this can cause the eval to fail unless the live environment (k8s cluster) matches what the LLM expects.

Run specific test suite:
```bash
pytest ./tests/llm/test_ask_holmes.py
pytest ./tests/llm/test_investigate.py
```

Run a specific test case:
```bash
pytest ./tests/llm/test_ask_holmes.py -k "01_how_many_pods"
```

### Environment Variables

Configure evaluations using these environment variables:

| Variable | Example | Description |
|----------|---------|-------------|
| `MODEL` | `MODEL=anthropic/claude-3.5` | Specify which LLM model to use |
| `CLASSIFIER_MODEL` | The LLM model to use for scoring the answer (LLM as judge). Defaults to `MODEL` |
| `ITERATIONS` | `ITERATIONS=3` | Run each test multiple times for consistency checking |
| `RUN_LIVE` | `RUN_LIVE=true` | Execute `before-test` and `after-test` commands, ignore mock files |
| `BRAINTRUST_API_KEY` | `BRAINTRUST_API_KEY=sk-1dh1...swdO02` | API key for Braintrust integration |
| `UPLOAD_DATASET` | `UPLOAD_DATASET=true` | Sync dataset to Braintrust (safe, separated by branch) |
| `PUSH_EVALS_TO_BRAINTRUST` | `PUSH_EVALS_TO_BRAINTRUST=true` | Upload evaluation results to Braintrust |
| `EXPERIMENT_ID` | `EXPERIMENT_ID=my_baseline` | Custom experiment name for result tracking |

### Simple Example

Run a comprehensive evaluation:
```bash
export MODEL=gpt-4o

# Run with parallel execution for speed
pytest -n 10 ./tests/llm/test_*.py
```

### Live Testing

For tests that require actual Kubernetes resources:
```bash
export RUN_LIVE=true

pytest ./tests/llm/test_ask_holmes.py -k "specific_test"
```

Live testing requires a Kubernetes cluster and will execute `before-test` and `after-test` commands to set up/tear down resources. Not all tests support live testing. Some tests require manual setup.

## Model Comparison Workflow

1. **Create Baseline**: Run evaluations with a reference model
   ```bash
   EXPERIMENT_ID=baseline_gpt4o MODEL=gpt-4o pytest -n 10 ./tests/llm/test_*
   ```

2. **Test New Model**: Run evaluations with the model you want to compare
   ```bash
   EXPERIMENT_ID=test_claude35 MODEL=anthropic/claude-3.5 pytest -n 10 ./tests/llm/test_*
   ```

3. **Compare Results**: Use Braintrust dashboard to analyze performance differences

## Writing Evaluations

For detailed information on creating new evaluations, see the [Writing Evaluations Guide](evals-writing.md).

## Reporting and Analysis

Learn how to analyze evaluation results using Braintrust in the [Reporting Guide](evals-reporting.md).

## Troubleshooting

### Common Issues

1. **Missing BRAINTRUST_API_KEY**: Some tests are skipped without this key
2. **Live test failures**: Ensure Kubernetes cluster access and proper permissions
3. **Mock file mismatches**: Regenerate mocks with `generate_mocks: true`
4. **Timeout errors**: Increase test timeout or check network connectivity

### Debug Mode

Enable verbose output:
```bash
pytest -v -s ./tests/llm/test_ask_holmes.py -k "specific_test"
```

This shows detailed output including:
- Expected vs actual results
- Tool calls made by the LLM
- Evaluation scores and rationales
- Debugging information