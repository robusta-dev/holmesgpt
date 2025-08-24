#!/usr/bin/env python3
"""Generate markdown report from eval results."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, DefaultDict, Set
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate markdown report from eval results"
    )
    parser.add_argument("--json-file", required=True, help="Path to JSON results file")
    parser.add_argument(
        "--output-file", required=True, help="Path to output markdown file"
    )
    parser.add_argument("--models", help="Comma-separated list of models tested")
    return parser.parse_args()


def load_results(json_file: Path) -> Dict[str, Any]:
    """Load results from pytest JSON report or custom format."""
    with open(json_file, "r") as f:
        data = json.load(f)

    # Handle different JSON formats
    if "tests" in data:
        # pytest-json-report format
        return parse_pytest_json(data)
    else:
        # Custom format from our reporter
        return data


def parse_pytest_json(data: Dict) -> Dict[str, Any]:
    """Parse pytest-json-report format."""
    results = {
        "summary": {
            "total": data["summary"]["total"],
            "passed": data["summary"].get("passed", 0),
            "failed": data["summary"].get("failed", 0),
            "skipped": data["summary"].get("skipped", 0),
        },
        "tests": [],
        "duration": data.get("duration", 0),
    }

    for test in data.get("tests", []):
        test_result = {
            "nodeid": test["nodeid"],
            "outcome": test["outcome"],
            "duration": test.get("duration", 0),
        }

        # Extract test case name and model from nodeid
        if "[" in test["nodeid"] and "]" in test["nodeid"]:
            params = test["nodeid"].split("[")[1].split("]")[0]
            # Parse out test case and model
            parts = params.split("-")
            if len(parts) >= 2:
                test_result["test_case"] = parts[0]
                test_result["model"] = "-".join(parts[1:])
            else:
                test_result["test_case"] = params
                test_result["model"] = "unknown"

        results["tests"].append(test_result)

    return results


def generate_summary_table(results: Dict[str, Any], models: List[str]) -> str:
    """Generate summary table by model."""
    model_stats: DefaultDict[str, Dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    )

    for test in results.get("tests", []):
        model = test.get("model", "unknown")
        outcome = test.get("outcome", "unknown")

        model_stats[model]["total"] += 1
        if outcome == "passed":
            model_stats[model]["passed"] += 1
        elif outcome == "failed":
            model_stats[model]["failed"] += 1
        elif outcome == "skipped":
            model_stats[model]["skipped"] += 1

    # Build markdown table
    lines = []
    lines.append("| Model | Pass | Fail | Skip | Total | Success Rate |")
    lines.append("|-------|------|------|------|-------|--------------|")

    for model in sorted(model_stats.keys()):
        stats = model_stats[model]
        total = stats["total"]
        passed = stats["passed"]
        failed = stats["failed"]
        skipped = stats["skipped"]

        # Calculate success rate (excluding skipped)
        valid_tests = total - skipped
        success_rate = (passed / valid_tests * 100) if valid_tests > 0 else 0

        # Format model name for display
        display_model = model.replace("anthropic/", "").replace("-20241022", "")
        if len(display_model) > 30:
            display_model = display_model[:27] + "..."

        # Add emoji indicator based on success rate
        if success_rate >= 95:
            indicator = "🟢"
        elif success_rate >= 80:
            indicator = "🟡"
        else:
            indicator = "🔴"

        lines.append(
            f"| {display_model} | {passed} | {failed} | {skipped} | {total} | "
            f"{indicator} {success_rate:.1f}% |"
        )

    return "\n".join(lines)


def generate_detailed_results(results: Dict[str, Any]) -> str:
    """Generate detailed test results grouped by test case."""
    test_cases: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for test in results.get("tests", []):
        test_case = test.get("test_case", "unknown")
        model = test.get("model", "unknown")
        outcome = test.get("outcome", "unknown")
        duration = test.get("duration", 0)

        test_cases[test_case][model] = {
            "outcome": outcome,
            "duration": duration,
        }

    # Get all unique models
    all_models: Set[str] = set()
    for test_case_results in test_cases.values():
        all_models.update(test_case_results.keys())

    sorted_models = sorted(all_models)

    # Build detailed table
    lines = []
    lines.append("\n### Detailed Test Results\n")
    lines.append("| Test Case | " + " | ".join(sorted_models) + " |")
    lines.append("|-----------|" + "|".join(["-------"] * len(sorted_models)) + "|")

    for test_case in sorted(test_cases.keys()):
        row = [test_case]
        for model in sorted_models:
            if model in test_cases[test_case]:
                result = test_cases[test_case][model]
                outcome = result["outcome"]
                duration = result["duration"]

                # Format cell with outcome and time
                if outcome == "passed":
                    cell = f"✅ ({duration:.1f}s)"
                elif outcome == "failed":
                    cell = f"❌ ({duration:.1f}s)"
                elif outcome == "skipped":
                    cell = "⏭️"
                else:
                    cell = "?"
            else:
                cell = "-"

            row.append(cell)

        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def generate_test_categories(results: Dict[str, Any]) -> str:
    """Generate test categories section."""
    categories: Dict[str, List[str]] = {
        "infrastructure": [],
        "observability": [],
        "troubleshooting": [],
        "performance": [],
        "configuration": [],
    }

    # Categorize tests based on naming patterns
    for test in results.get("tests", []):
        test_case = test.get("test_case", "")

        if any(
            word in test_case.lower()
            for word in ["pod", "node", "deployment", "service"]
        ):
            categories["infrastructure"].append(test_case)
        elif any(
            word in test_case.lower()
            for word in ["metric", "log", "trace", "prometheus", "grafana"]
        ):
            categories["observability"].append(test_case)
        elif any(
            word in test_case.lower()
            for word in ["crash", "error", "fail", "issue", "problem"]
        ):
            categories["troubleshooting"].append(test_case)
        elif any(
            word in test_case.lower()
            for word in ["latency", "memory", "cpu", "performance"]
        ):
            categories["performance"].append(test_case)
        else:
            categories["configuration"].append(test_case)

    lines = []
    lines.append("\n### Test Categories\n")

    for category, tests in categories.items():
        if tests:
            unique_tests = list(set(tests))
            lines.append(
                f"**{category.title()}** ({len(unique_tests)} tests): "
                f"{', '.join(sorted(unique_tests)[:5])}"
                f"{'...' if len(unique_tests) > 5 else ''}"
            )

    return "\n".join(lines)


def main():
    args = parse_args()

    # Load results
    results = load_results(Path(args.json_file))

    # Parse models
    models = args.models.split(",") if args.models else []

    # Generate report sections
    report_lines = []

    # Header
    report_lines.append("# HolmesGPT LLM Evaluation Benchmark Results")
    report_lines.append("")
    report_lines.append(
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    report_lines.append(f"**Total Duration**: {results.get('duration', 0):.1f} seconds")
    report_lines.append("")

    # Executive summary
    report_lines.append("## Executive Summary")
    report_lines.append("")
    report_lines.append(
        "HolmesGPT is continuously evaluated against a comprehensive suite of "
        "real-world Kubernetes troubleshooting scenarios. Our benchmarks test "
        "the system's ability to diagnose issues, analyze observability data, "
        "and provide actionable insights."
    )
    report_lines.append("")

    # Model comparison table
    report_lines.append("## Model Performance Comparison")
    report_lines.append("")
    report_lines.append(generate_summary_table(results, models))
    report_lines.append("")

    # Test environment
    report_lines.append("## Test Environment")
    report_lines.append("")
    report_lines.append("- **Platform**: Kubernetes v1.27+")
    report_lines.append("- **Observability Stack**: Prometheus, Grafana, Loki")
    report_lines.append(
        "- **Test Types**: Infrastructure diagnostics, log analysis, metric queries, troubleshooting"
    )
    report_lines.append("- **Evaluation Method**: LLM-as-judge with GPT-4 verification")
    report_lines.append("")

    # Test categories
    report_lines.append(generate_test_categories(results))
    report_lines.append("")

    # Detailed results
    report_lines.append(generate_detailed_results(results))
    report_lines.append("")

    # Methodology
    report_lines.append("## Evaluation Methodology")
    report_lines.append("")
    report_lines.append(
        "1. **Real-world scenarios**: Each test represents actual production issues"
    )
    report_lines.append(
        "2. **Multi-tool integration**: Tests require using multiple observability tools"
    )
    report_lines.append(
        "3. **Correctness scoring**: Responses evaluated for accuracy and completeness"
    )
    report_lines.append(
        "4. **Performance tracking**: Execution time measured for each test"
    )
    report_lines.append("")

    # Footer
    report_lines.append("---")
    report_lines.append(
        "*Results are automatically generated and updated weekly. "
        "For detailed traces and analysis, see our [Braintrust dashboard](https://braintrust.dev).*"
    )

    # Write report
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines))
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
