# Large-Scale Logging Evaluations (66-75)

## Overview
Successfully implemented 10 challenging logging evaluations that test Holmes' ability to analyze logs exceeding the LLM context window. Each evaluation generates 100,000+ log entries (20-30MB) with specific patterns or errors strategically placed.

## Implementation Summary

| Eval | Name | Pattern | Error Location | Key Challenge |
|------|------|---------|----------------|---------------|
| 66 | HTTP Error Needle | 1 error in 100K requests | Middle (50%) | Finding single anomaly in massive haystack |
| 67 | Performance Degradation | Response time 100ms→5s→timeout | Throughout | Recognizing gradual degradation pattern |
| 68 | Cascading Failures | Redis→Auth→User→Order→Payment | Beginning (10%) | Tracing root cause across services |
| 69 | Rate Limit Exhaustion | Traffic spike causes 429 errors | End (80%) | Identifying trigger before errors |
| 70 | Memory Leak | Memory growth 100MB→4GB→OOM | Throughout | Long-term trend analysis |
| 71 | Connection Pool | Pool exhaustion at 100/100 | Middle (60%) | Resource saturation detection |
| 72 | Distributed Trace | Order ORD-12345 failure trace | Scattered | Multi-service correlation |
| 73 | Time Window | Errors only 03:00-03:05 | Specific time | Time-based pattern recognition |
| 74 | Config Change | Cache TTL 3600→60 causes issues | Middle (50%) | Before/after comparison |
| 75 | Network Flapping | Timeout rate 0.1%→1%→10%→60% | Throughout | Worsening degradation pattern |

## Technical Implementation

Each evaluation follows the same structure:
1. **Python Script** (`generate_logs.py`): Generates specific log patterns
2. **Kubernetes Secret**: Stores the Python script
3. **Pod Deployment**: Runs Python script to output logs
4. **Test Configuration**: Defines the question and expected answers

### Key Features:
- **Large Volume**: Each test generates 100,000+ log entries
- **Strategic Placement**: Errors/patterns placed at beginning, middle, end, or throughout
- **Realistic Patterns**: Based on common production issues
- **Context Window Challenge**: Forces intelligent searching vs brute force

### Resource Requirements:
- Memory: 256-512MB per pod
- CPU: 100-200m per pod
- Startup time: 30-50 seconds for log generation

## Running the Tests

To run all new logging evaluations:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "66_|67_|68_|69_|70_|71_|72_|73_|74_|75_" -v
```

To run a specific evaluation:
```bash
poetry run pytest "tests/llm/test_ask_holmes.py::test_ask_holmes[66_http_error_needle]" -v
```

To generate mocks for these tests:
```bash
poetry run pytest tests/llm/test_ask_holmes.py -k "66_|67_|68_|69_|70_|71_|72_|73_|74_|75_" --generate-mocks
```

## Expected Behaviors

1. **Search Strategy**: Holmes should use targeted searches based on the question
2. **Pattern Recognition**: Identify trends and anomalies in large datasets
3. **Correlation**: Connect related events across time and services
4. **Time Analysis**: Recognize time-based patterns and windows
5. **Root Cause**: Trace cascading failures to their source

## Notes

- All evaluations are tagged with `logs` and `context_window`
- Additional tags applied based on specific patterns (e.g., `datetime`, `network`, `chain-of-causation`)
- Each test validates that Holmes finds the specific issue without loading entire log files
- Mock files will need to be generated using `--generate-mocks` flag before running in CI
