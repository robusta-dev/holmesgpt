# Writing Evaluations

This guide explains how to create new evaluations for HolmesGPT. Evaluations test the system's ability to correctly diagnose issues and provide accurate recommendations.

- [Evaluations Overview](index.md) - Introduction to HolmesGPT's evaluation system
- [Reporting with Braintrust](reporting.md) - Analyze results and debug failures using Braintrust

## Overview

HolmesGPT supports two types of evaluations:

1. **Ask Holmes Tests**: Chat-like interactions (`tests/llm/test_ask_holmes.py`)
2. **Investigation Tests**: Issue analysis for events triggered by AlertManager (`tests/llm/test_investigate.py`)

Each test consists of:
- A test case definition (`test_case.yaml`)
- Mock tool outputs (e.g., `kubectl_describe.txt`)
- Optional Kubernetes manifests for live testing
- Optional custom toolset configurations

## High-Level Steps

1. **Choose test type**: Ask Holmes vs Investigation. Choose Ask Holmes for most use cases. Choose Investigations for issues triggered by AlertManager
2. **Create a test folder**: Use numbered naming convention
3. **Define your test case**:
  * Create `test_case.yaml` with prompt and expectations
  * Define kubectl or helm setup and teardown manifests
4. **Generate mock data**: Using a live system
5. **Set evaluation criteria**: Define minimum scores for test success
6. **Test and iterate**: Run the test and refine as needed

## Step-by-Step Example: Creating an Ask Holmes Test

Let's create a simple test that asks about pod health status.

### Step 1: Create Test Folder

```bash
mkdir tests/llm/fixtures/test_ask_holmes/99_pod_health_check
cd tests/llm/fixtures/test_ask_holmes/99_pod_health_check
```

### Step 2: Create test_case.yaml

```yaml
user_prompt: 'Is the nginx pod healthy?'
expected_output:
  - nginx pod is healthy
evaluation:
  correctness: 1
before_test: kubectl apply -f ./manifest.yaml
after_test: kubectl delete -f ./manifest.yaml
```

- `user_prompt`: This is the question that will trigger Holmes' investigation
- `expected_output`: This is a list of expected elements that MUST be found in Holmes' answer. The combination of these elements lead to a `correctness` score based on HolmesGPT's output. This `expected_output` will be compared against HolmesGPT's answer and evaluated by a LLM ('LLM as judge'). The resulting score is called `correctness` and is a binary score with a value of either `0` or `1`. HolmesGPT's answer is score `0` is any of the expected element is not present in the answer, `1` if all expected elements are preent in the answer.
- `evaluation.correctness`: This is the expected correctness score and is used for pytest to fail the test. This expected `correctness` score should be `0` unless you expect HolmesGPT to systematically succeed the evaluation. Because of this, it is important for `expected_output` to be reduced to the minimally accepted output from HolmesGPT.
- `before_test` and `after_test`: These are setup and teardown steps to reproduce the test on a fresh environment. It is important for these to be present because as HolmesGPT's code, prompt and toolset evolve the mocks become insufficient or inaccurate. These scripts are run automatically when the env var `RUN_LIVE=true` is set


### Step 3: Generate Mock Tool Outputs

Create mock files that simulate kubectl command outputs.

The best way to do this is to:

1. Deploy the test case you want to build an eval for in a kubernetes cluster (run the `before_test` script manually)
2. Configure HolmesGPT to connect to the cluster (via kubectl and any other relevant toolsets)
3. Enable the auto generation of mock files by using the `--generate-mocks` CLI flag
4. Repeatedly run the eval with `ITERATIONS=100 pytest tests/llm/test_ask_holmes.py -k 99_pod_health_check --generate-mocks`

### Step 4: Run the Test

```bash
pytest ./tests/llm/test_ask_holmes.py -k "99_pod_health_check" -v
```

## Test Case Configuration Reference

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_prompt` | string | Yes | The question or prompt for HolmesGPT |
| `expected_output` | string or list | Yes | Expected elements in the response |
| `evaluation` | dict | No | Minimum scores for test to pass |

### Ask Holmes Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `before_test` | string | Command to run before test (requires `RUN_LIVE=true`) |
| `after_test` | string | Command to run after test cleanup |

### Investigation Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `expected_sections` | dict | Required/prohibited sections in output |

### Example: Complex Investigation Test

```yaml
user_prompt: "Investigate this CrashLoopBackOff issue"
expected_output:
  - Pod is experiencing CrashLoopBackOff
  - Container exits with code 1 due to configuration error
  - Missing environment variable DATABASE_URL
expected_sections:
  "Root Cause Analysis":
    - CrashLoopBackOff
    - configuration error
  "Recommended Actions": true
  "External Links": false
evaluation:
  correctness: 0
before_test: kubectl apply -f ./manifest.yaml
after_test: kubectl delete -f ./manifest.yaml
```

## Mock File Generation

### Automatic Generation

Use the `--generate-mocks` CLI flag and run with a live cluster:

```bash
ITERATIONS=100 pytest ./tests/llm/test_ask_holmes.py -k "your_test" --generate-mocks
```

Or to regenerate all existing mocks for consistency:

```bash
pytest ./tests/llm/test_ask_holmes.py -k "your_test" --regenerate-all-mocks
```

This captures real tool outputs and saves them as mock files.

### Manual Creation

Create files matching the tool names used by HolmesGPT:

- `kubectl_describe.txt` - Pod/resource descriptions
- `kubectl_logs.txt` - Container logs
- `kubectl_events.txt` - Kubernetes events
- `prometheus_query.txt` - Metrics data
- `fetch_loki_logs.txt` - Log aggregation results

### Naming Convention

Mock files follow the pattern: `{tool_name}_{additional_context}.txt`

Examples:
- `kubectl_describe_pod_nginx_default.txt`
- `kubectl_logs_all_containers_nginx.txt`
- `execute_prometheus_range_query.txt`

## Advanced Test Configuration

### Toolset Configuration

Control which toolsets are available for a specific test by creating a `toolsets.yaml` file in the test directory:

```yaml
toolsets:
  kubernetes/core:
    enabled: true

  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: "http://custom-prometheus:9090"
      prometheus_username: "admin"
      prometheus_password: "secretpass"

  grafana/dashboards:
    enabled: false  # Explicitly disable toolsets

  # Enable non-default toolsets
  rabbitmq/core:
    enabled: true
    config:
      clusters:
        - id: rabbitmq-test
          username: guest
          password: guest
          management_url: http://rabbitmq:15672
```

Use cases:
- Test with limited toolsets available
- Provide custom configuration (URLs, credentials)
- Simulate environments where certain tools are unavailable
- Test error handling when expected tools are disabled

### Mock Policy Control

Control mock behavior on a per-test basis by adding `mock_policy` to `test_case.yaml`:

```yaml
user_prompt: "Check cluster health"
mock_policy: "always_mock"  # Options: always_mock, never_mock, inherit
expected_output:
  - Cluster is healthy
```

Options:
- **`inherit`** (default): Use global settings from environment/CLI flags
  - Recommended for most tests
  - Allows flexibility to run with or without mocks based on environment

- **`never_mock`**: Force live execution
  - Test automatically skipped if `RUN_LIVE` is not set
  - Ensures the test always runs against real tools
  - Verifies actual tool behavior and integration
  - Preferred when you want to guarantee realistic testing

- **`always_mock`**: Always use mock data, even with `RUN_LIVE=true`
  - Ensures deterministic behavior
  - Use only when live testing is impractical (e.g., complex cluster setups, specific error conditions)
  - Note: You should prefer `inherit` or `never_mock` when possible as they test the agent more realistically and are less fragile

### Custom Runbooks

Override the default runbook catalog for specific tests by adding a `runbooks` field to `test_case.yaml`:

```yaml
user_prompt: "I'm experiencing DNS resolution issues in my kubernetes cluster"
expected_output:
  - DNS troubleshooting runbook
  - fetch_runbook

# Custom runbook catalog
runbooks:
  catalog:
    - update_date: "2025-07-26"
      description: "Runbook for troubleshooting DNS issues in Kubernetes"
      link: "k8s-dns-troubleshooting.md"
    - update_date: "2025-07-26"
      description: "Runbook for debugging pod crashes"
      link: "pod-crash-debug.md"
```

The runbook markdown files (e.g., `k8s-dns-troubleshooting.md`) should be placed in the same directory as `test_case.yaml`.

Options:
- **No `runbooks` field**: Use default system runbooks
- **`runbooks: {}`**: Empty catalog (no runbooks available)
- **`runbooks: {catalog: [...]}`**: Custom runbook catalog

This is useful for:
- Testing runbook selection logic
- Verifying behavior when no runbooks are available
- Testing custom troubleshooting procedures
- Ensuring proper runbook following

### Example Tests

The repository includes example tests demonstrating each feature:

- `_EXAMPLE_01_toolsets_config/` - Toolset configuration
- `_EXAMPLE_02_mock_policy_always/` - Always use mocks
- `_EXAMPLE_03_mock_policy_never/` - Force live execution
- `_EXAMPLE_04_custom_runbooks/` - Custom runbook configuration
- `_EXAMPLE_05_mock_generation/` - Mock generation workflow
- `_EXAMPLE_06_combined_features/` - Combining multiple features

Run examples:
```bash
pytest tests/llm/test_ask_holmes.py -k "_EXAMPLE" -v
```

## Live Testing with Real Resources

For tests that need actual Kubernetes resources:

### Step 1: Create Manifest

**manifest.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-nginx
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-nginx
  template:
    metadata:
      labels:
        app: test-nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.20
        ports:
        - containerPort: 80
```

### Step 2: Configure Setup/Teardown

```yaml
user_prompt: 'How is the test-nginx deployment performing?'
before-test: kubectl apply -f manifest.yaml
after-test: kubectl delete -f manifest.yaml
# ... rest of configuration
```

### Step 3: Run Live Test

```bash
RUN_LIVE=true pytest ./tests/llm/test_ask_holmes.py -k "your_test"
```

> `RUN_LIVE` is currently incompatible with `ITERATIONS` > 1.

## Evaluation Scoring

### Correctness Score

Measures how well the output matches expected elements:
- 1: Match
- 0: Mismatch

### Setting Minimum Scores

```yaml
evaluation:
  correctness: 1
```

## Tagging

Evals are tagged for organisation and reporting purposes.
The valid tags are defined in the test constants file in the repository.

## Best Practices

### Test Design
1. **Start simple**: Begin with basic scenarios before complex edge cases
2. **Clear expectations**: Write specific, measurable expected outputs
3. **Realistic scenarios**: Base tests on actual user problems
4. **Incremental complexity**: Build from simple to complex test cases

### Mock Data Quality
1. **Representative data**: Use realistic kubectl outputs and logs
2. **Error scenarios**: Include failure modes and edge cases
3. **Consistent formatting**: Match actual tool output formats
4. **Sufficient detail**: Include enough information for proper diagnosis
5. **Run repeatedly**: Run mock generation many times to ensure all investigative paths are covered by mock files

## Troubleshooting Test Creation

### Common Issues

**Test always fails with low correctness score**:
- Check if expected_output matches actual LLM capabilities
- Verify mock data provides sufficient information
- Consider lowering score threshold temporarily

**Missing tool outputs**:
- Ensure mock files are named correctly
- Check that required toolsets are enabled
- Verify mock file content is properly formatted

**Inconsistent results**:
- Run multiple iterations: `ITERATIONS=5`
- Check for non-deterministic elements in prompts
- Consider using temperature=0 for more consistent outputs

### Debugging Commands

```bash
# Verbose output showing all details
pytest -v -s ./tests/llm/test_ask_holmes.py -k "your_test"

# Generate fresh mocks from live system
pytest ./tests/llm/test_ask_holmes.py -k "your_test" --generate-mocks

# Or regenerate ALL mocks to ensure consistency
pytest ./tests/llm/test_ask_holmes.py -k "your_test" --regenerate-all-mocks

# Skip setup/cleanup for faster debugging
pytest ./tests/llm/test_ask_holmes.py -k "your_test" --skip-setup --skip-cleanup

# Run with specific number of iterations
ITERATIONS=10 pytest ./tests/llm/test_ask_holmes.py -k "your_test"
```

### CLI Flags Reference

**Custom HolmesGPT Flags:**
- `--generate-mocks` - Generate mock files during test execution
- `--regenerate-all-mocks` - Regenerate all mock files (implies --generate-mocks)
- `--skip-setup` - Skip `before_test` commands
- `--skip-cleanup` - Skip `after_test` commands

**Common Pytest Flags:**
- `-n <number>` - Run tests in parallel
- `-k <pattern>` - Run tests matching pattern
- `-m <marker>` - Run tests with specific marker
- `-v/-vv` - Verbose output
- `-s` - Show print statements
- `--no-cov` - Disable coverage
- `--collect-only` - List tests without running

This completes the evaluation writing guide. The next step is setting up reporting and analysis using Braintrust.
