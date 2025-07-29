# DataDog Logs Toolset Evaluation Tests

This directory contains evaluation tests for the DataDog logs toolset integration with HolmesGPT.

## Test Cases

### 110_datadog_end_time_null
**Issue**: Tests the bug where end_time is null
- **Namespace**: app-110
- **Pod**: ocean-voyager
- **Expected**: Error handling for null end_time

### 111_datadog_end_time_zero
**Issue**: Tests the bug where end_time is 0
- **Namespace**: app-111
- **Pod**: arctic-explorer
- **Expected**: Error handling for end_time = 0

### 112_datadog_datetime_no_logs
**Issue**: Tests when datetime is correct but no logs are returned
- **Namespace**: app-112
- **Pod**: mountain-climber-7d5f8c9b4-x3nkp
- **Expected**: Empty logs response handling

### 113_datadog_toolset_recognition
**Issue**: Tests that Holmes recognizes DataDog as a logs provider
- **Namespace**: app-113
- **Pod**: desert-nomad
- **Expected**: Holmes should recognize DataDog toolset when user asks for "datadog logs"

### 114_datadog_pod_logs_work
**Issue**: Tests that fetching pod logs through DataDog works correctly
- **Namespace**: app-114
- **Pod**: river-dancer-8b6f9c5d7-q2wsz
- **Expected**: Successfully returns logs

### 115_datadog_last_60_minutes
**Issue**: Tests fetching logs for the last 60 minutes
- **Namespace**: app-115
- **Pod**: forest-guardian-7c8d9f6b4-k3lpq
- **Expected**: Returns logs from the last hour

### 116_datadog_last_24_hours
**Issue**: Tests fetching logs for the last 24 hours
- **Namespace**: app-116
- **Deployment**: sky-watcher
- **Expected**: Returns logs from the last day

### 117_datadog_default_time
**Issue**: Tests default time behavior when no time is specified
- **Namespace**: app-117
- **Pod**: wind-chaser-9d7f8c5b6-h4jkl
- **Expected**: Returns logs using default time span (1 hour)

## Common Configuration

All tests use the following DataDog configuration:
```yaml
toolsets:
  datadog/logs:
    enabled: true
    config:
      dd_api_key: "test-api-key"
      dd_app_key: "test-app-key"
      site_api_url: "https://api.datadoghq.com"
```

## Running the Tests

To run all DataDog tests:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "datadog" -v
```

To run a specific test:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "110_datadog_end_time_null" -v
```

## Notes

- All tests include a healthcheck mock file (`fetch_pod_logs_*_*_1_-172800.txt`) required for DataDog toolset initialization
- Tests use unique namespaces (app-XXX where XXX is the test number) to avoid conflicts
- Mock files follow the pattern: `fetch_pod_logs_<namespace>_<pod_name>_<additional_params>.txt`
