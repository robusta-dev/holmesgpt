# LLM Benchmarks

## Latest Results

**[View latest benchmark results →](./latest-results.md)**

Weekly automated tests across 150+ real-world Kubernetes and cloud-native troubleshooting scenarios.

## Test Suite

- **150+ total tests**: including root-cause analysis scenarios, user Q&A, AlertManager investigations, and more
- **Coverage**: Kubernetes troubleshooting, log analysis, database issues, cloud infrastructure
- **Validation**: LLM-as-judge validates expected outputs
- **Key markers**: `easy` (regression tests), `medium`, `hard` (challenging scenarios), `logs`, `kubernetes`, `database`

## Automated Benchmarking

Our CI/CD pipeline automatically runs benchmarks:
- **Weekly** - Every Sunday at 2 AM UTC (comprehensive testing with 10 iterations)
- **Pull Requests** - When eval-related files are modified (quick validation)
- **On-demand** - Via GitHub Actions UI

Results are automatically published here and archived in `history/`.

## Running Benchmarks

Want to run benchmarks yourself or contribute new tests?

**[→ See the Evaluation Guide](../development/evals/index.md)** for complete instructions on:
- Running benchmarks locally
- Testing different models
- Adding new test scenarios
- Debugging failures

## Related

- [Adding New Evals](../development/evals/adding-new-eval.md) - Contribute test scenarios
- [Braintrust Reporting](../development/evals/reporting.md) - Analyze results in detail
