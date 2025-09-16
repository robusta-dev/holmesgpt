# Using Mock Data in LLM Tests

This document describes mock data usage in HolmesGPT's LLM evaluation tests. **Live evaluations (`RUN_LIVE=true`) are strongly preferred** because they're more reliable and accurate.

## Why Live Evaluations Are Preferred

**LLMs can take multiple paths to reach the same conclusion.** When using mock data:
- The LLM might call tools in a different order than when mocks were generated
- It might use different tool combinations to diagnose the same issue
- It might ask for additional information not captured in the mocks
- Mock data represents only one possible investigation path

With live evaluations, the LLM can explore any path it chooses, making tests more robust and realistic.

## When Mock Data Is Necessary

Mock data is sometimes unavoidable:
- CI/CD environments without Kubernetes cluster access
- Testing specific edge cases that require controlled responses
- Reproducing exact historical scenarios

**Important**: Even when using mocks, always validate with `RUN_LIVE=true` in a real environment.

## Mock Data Structure

Mock files are stored in `tests/llm/fixtures/{test_name}/` directories:
- Each test has mock tool responses and expected outputs
- Mock responses are YAML files matching tool names
- Uses LLM-as-judge for automated evaluation

## Generating Mock Data

```bash
# Generate mocks for a specific test
poetry run pytest tests/llm/test_ask_holmes.py -k "test_name" --generate-mocks

# Regenerate all mock files
poetry run pytest tests/llm/test_ask_holmes.py --regenerate-all-mocks
```

## Mock Data Guidelines

When creating mock data:
- Never generate mock data manually - always use `--generate-mocks` with live execution
- Mock data should match real-world responses exactly
- Include all fields that would be present in actual responses
- Maintain proper timestamps and data relationships

## Important Notes

- **Mock data captures only one investigation path** - LLMs may take completely different approaches to reach the same conclusion
- Tests with mocks often fail when the LLM chooses a different but equally valid investigation strategy
- Mock execution misses the dynamic nature of real troubleshooting
- Always develop and validate tests with `RUN_LIVE=true`
- Mock data becomes stale as APIs and tool behaviors evolve

## Testing Workflow

1. Develop test with `RUN_LIVE=true`
2. Generate mocks if needed: `--generate-mocks`
3. Validate mock execution matches live behavior
4. Always use `RUN_LIVE=true` for final validation
