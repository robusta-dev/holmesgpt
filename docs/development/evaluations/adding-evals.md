# Adding a New Eval

Create test cases that measure HolmesGPT's diagnostic accuracy and help track improvements over time.

## Test Types

- **Ask Holmes**: Chat-like Q&A interactions
- **Investigation**: AlertManager event analysis

## Quick Start

1. Create test folder: `tests/llm/fixtures/test_ask_holmes/99_your_test/`

2. Create `test_case.yaml`:
```yaml
user_prompt: 'Is the nginx pod healthy?'
expected_output:
  - nginx pod is healthy
before_test: kubectl apply -f ./manifest.yaml
after_test: kubectl delete -f ./manifest.yaml
```

3. Create `manifest.yaml` with your test scenario:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  namespace: default
spec:
  containers:
  - name: nginx
    image: nginx:latest
    ports:
    - containerPort: 80
```

4. Run test:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "99_your_test" -v
```

## Test Configuration

### Required Fields
- `user_prompt`: Question for Holmes
- `expected_output`: List of required elements in response
- `before_test`/`after_test`: Setup/teardown commands (run with `RUN_LIVE=true`)

### Optional Fields
- `tags`: List of test markers (e.g., `[easy, kubernetes, logs]`)
- `skip`: Boolean to skip test
- `skip_reason`: Explanation why test is skipped
- `mocked_date`: Override system time for test (e.g., `"2025-06-23T11:34:00Z"`)
- `cluster_name`: Specify kubernetes cluster name
- `include_files`: List of files to include in context (like CLI's `--include` flag)
- `runbooks`: Override runbook catalog:
  ```yaml
  runbooks:
    catalog:
      - description: "Database Connection Troubleshooting"
        link: "database_troubleshooting.md"
        update_date: "2025-07-01"
  ```
- `toolsets`: Configure toolsets (can also use separate `toolsets.yaml` file):
  ```yaml
  toolsets:
    aws/lambda:
      enabled: true
    aws/cloudwatch:
      enabled: false
  ```
- `port_forwards`: Configure port forwarding for tests
- `test_env_vars`: Environment variables during test execution
- `mock_policy`: Control mock behavior (`always_mock`, `never_mock`, or `inherit`)
- `conversation_history`: For multi-turn conversation tests
- `expected_sections`: For investigation tests only

## Mock Data Usage

**Live evaluations (`RUN_LIVE=true`) are strongly preferred** because they're more reliable and accurate.

### Why Live Evaluations Are Preferred

**LLMs can take multiple paths to reach the same conclusion.** When using mock data:
- The LLM might call tools in a different order than when mocks were generated
- It might use different tool combinations to diagnose the same issue
- It might ask for additional information not captured in the mocks
- Mock data represents only one possible investigation path

With live evaluations, the LLM can explore any path it chooses, making tests more robust and realistic.

### When Mock Data Is Necessary

Mock data is sometimes unavoidable:
- CI/CD environments without Kubernetes cluster access
- Testing specific edge cases that require controlled responses
- Reproducing exact historical scenarios

**Important**: Even when using mocks, always validate with `RUN_LIVE=true` in a real environment.

### Generating Mock Data

```bash
# Generate mocks for one test
poetry run pytest tests/llm/test_ask_holmes.py -k "your_test" --generate-mocks

# Remove any existing mocks for your test and generate them from scratch
poetry run pytest tests/llm/test_ask_holmes.py -k "your_test" --regenerate-all-mocks
```

Mock files are named: `{tool_name}_{context}.txt`

### Mock Data Guidelines

When creating mock data:
- Never generate mock data manually - always use `--generate-mocks` with live execution
- Mock data should match real-world responses exactly
- Include all fields that would be present in actual responses
- Maintain proper timestamps and data relationships

### Important Notes About Mocks

- **Mock data captures only one investigation path** - LLMs may take completely different approaches
- Tests with mocks often fail when the LLM chooses a different but equally valid investigation strategy
- Mock execution misses the dynamic nature of real troubleshooting
- Always develop and validate tests with `RUN_LIVE=true`
- Mock data becomes stale as APIs and tool behaviors evolve

## Advanced Features

### Toolsets Configuration

You can configure which toolsets are available during your test in two ways:

1. **Inline in test_case.yaml**:
```yaml
toolsets:
  kubernetes/core:
    enabled: true
  aws/cloudwatch:
    enabled: false
```

2. **Separate toolsets.yaml file** (preferred for complex configurations):
```yaml
# toolsets.yaml
toolsets:
  grafana/loki:
    enabled: true
    config:
      url: http://loki.app-143.svc.cluster.local:3100
      api_key: ""
  kafka/admin:
    enabled: true
    config:
      kafka_clusters:
        - name: "kafka"
          kafka_broker: "kafka:9092"
```

### Port Forwarding

Some tests require access to services that are not directly exposed. You can configure port forwards that will be automatically set up and torn down for your test:

```yaml
port_forwards:
  - namespace: app-01
    service: rabbitmq
    local_port: 15672
    remote_port: 15672
  - namespace: app-01
    service: prometheus
    local_port: 9090
    remote_port: 9090
```

**Note**: Use unique local ports across all tests to avoid conflicts

Port forwards are:

- Automatically started before any tests run
- Shared across all tests in a session to avoid conflicts
- Always cleaned up after tests complete, even if tests are interrupted
- Run regardless of `--skip-setup` or `--skip-cleanup` flags

**Important notes:**

- Use unique local ports across all tests to avoid conflicts
- Port forwards persist for the entire test session
- If a port is already in use, the test will fail with helpful debugging information
- Use `lsof -ti :<port>` to find processes using a port
- Port forwards work with both mock and live (`RUN_LIVE=true`) test modes

### Toolset Configuration

Create `toolsets.yaml` to customize available tools:

```yaml
toolsets:
  prometheus/metrics:
    enabled: true
    config:
      prometheus_url: "http://custom-prometheus:9090"
  grafana/dashboards:
    enabled: false  # Disable specific toolsets
```

### Mock Policy

```yaml
mock_policy: "inherit"  # Options: inherit (default), never_mock, always_mock
```

- `inherit`: Use global settings
- `never_mock`: Force live execution (skipped if RUN_LIVE not set)
- `always_mock`: Always use mocks (avoid when possible)

### Custom Runbooks

```yaml
runbooks:
  catalog:
    - description: "DNS troubleshooting"
      link: "dns-runbook.md"  # Place .md file in test directory
```

Options:

- No field: Use default runbooks
- `runbooks: {}`: No runbooks available
- `runbooks: {catalog: [...]}`: Custom catalog

## Tagging

Evals support tags for organization, filtering, and reporting purposes. Tags help categorize tests by their characteristics and enable selective test execution.

### Available Tags

The valid tags are defined in the test constants file in the repository.

Some examples

- `logs` - Tests HolmesGPT's ability to find and interpret logs correctly
- `context_window` - Tests handling of data that exceeds the LLM's context window
- `synthetic` - Tests that use manually generated mock data (cannot be run live)
- `datetime` - Tests date/time handling and interpretation
- etc.

### Using Tags in Test Cases

Add tags to your `test_case.yaml`:

```yaml
user_prompt: "Show me the logs for the pod `robusta-holmes` since last Thursday"
tags:
  - logs
  - datetime
expected_output:
  - Database unavailable
  - Memory pressure
```
