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
            "user_properties": test.get(
                "user_properties", []
            ),  # Include user_properties
            "call": test.get("call"),  # Include call for duration info
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


def generate_model_by_tag_table(results: Dict[str, Any]) -> str:
    """Generate a table showing model performance by tag."""
    # Collect data by model and tag
    model_tag_stats: DefaultDict[str, DefaultDict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"total": 0, "passed": 0})
    )

    all_tags: Set[str] = set()
    all_models: Set[str] = set()

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract model and tags from user_properties
        model = None
        tags = []

        user_props = test.get("user_properties", [])

        for prop in user_props:
            if isinstance(prop, dict):
                if "model" in prop:
                    model = prop["model"]
                if "tags" in prop:
                    tags = prop["tags"]

        if not model:
            # Fallback: try to extract from nodeid
            nodeid = test.get("nodeid", "")
            if "-" in nodeid:
                model = nodeid.split("-")[-1].rstrip("]")

        if model and tags:
            all_models.add(model)
            outcome = test.get("outcome", "unknown")

            for tag in tags:
                all_tags.add(tag)
                model_tag_stats[model][tag]["total"] += 1
                if outcome == "passed":
                    model_tag_stats[model][tag]["passed"] += 1

    if not all_tags or not all_models:
        return ""

    # Build the table with tags as rows and models as columns
    lines = []
    lines.append("## Performance by Tag")
    lines.append("")
    lines.append("Success rate by test category and model:")
    lines.append("")

    # Header with models as columns
    sorted_models = sorted(all_models)
    sorted_tags = sorted(all_tags)

    # Format model names for display
    display_models = []
    for model in sorted_models:
        display_model = model.replace("anthropic/", "").replace("-20241022", "")
        if len(display_model) > 15:
            display_model = display_model[:12] + "..."
        display_models.append(display_model)

    header = "| Tag | " + " | ".join(display_models) + " |"
    separator = "|-----|" + "-------|" * len(sorted_models)

    lines.append(header)
    lines.append(separator)

    # Data rows (one per tag)
    for tag in sorted_tags:
        row = [tag]

        for model in sorted_models:
            stats = model_tag_stats[model][tag]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = passed / total * 100
                # Add emoji based on rate
                if rate >= 95:
                    emoji = "🟢"
                elif rate >= 80:
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                cell = f"{emoji} {rate:.0f}% ({passed}/{total})"
            else:
                cell = "N/A"
            row.append(cell)

        lines.append("| " + " | ".join(row) + " |")

    # Add Overall row
    overall_row = ["**Overall**"]
    for model in sorted_models:
        total_passed = 0
        total_tests = 0
        for tag in sorted_tags:
            stats = model_tag_stats[model][tag]
            total_passed += stats["passed"]
            total_tests += stats["total"]

        if total_tests > 0:
            overall_rate = total_passed / total_tests * 100
            if overall_rate >= 95:
                emoji = "🟢"
            elif overall_rate >= 80:
                emoji = "🟡"
            else:
                emoji = "🔴"
            overall_row.append(
                f"{emoji} {overall_rate:.0f}% ({total_passed}/{total_tests})"
            )
        else:
            overall_row.append("N/A")

    lines.append("| " + " | ".join(overall_row) + " |")

    return "\n".join(lines)


def generate_detailed_results(results: Dict[str, Any]) -> str:
    """Generate detailed test results grouped by test case."""
    test_cases: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract test case from user_properties
        test_case = "unknown"
        model = "unknown"
        for prop in test.get("user_properties", []):
            if isinstance(prop, dict):
                if "clean_test_case_id" in prop:
                    test_case = prop["clean_test_case_id"]
                if "model" in prop:
                    model = prop["model"]

        # Fallback to nodeid parsing if needed
        if test_case == "unknown":
            nodeid = test.get("nodeid", "")
            if "[" in nodeid:
                test_case = nodeid.split("[")[1].split("-")[0]

        if model == "unknown":
            nodeid = test.get("nodeid", "")
            if "-" in nodeid:
                model = nodeid.split("-")[-1].rstrip("]")

        outcome = test.get("outcome", "unknown")
        duration = test.get("call", {}).get("duration", 0) if test.get("call") else 0

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


def generate_latency_comparison_table(results: Dict[str, Any]) -> str:
    """Generate model latency comparison table."""
    model_timings: DefaultDict[str, List[float]] = defaultdict(list)

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract model and duration from user_properties and test data
        model = None
        duration = test.get("call", {}).get("duration", 0) if test.get("call") else 0

        user_props = test.get("user_properties", [])
        for prop in user_props:
            if isinstance(prop, dict) and "model" in prop:
                model = prop["model"]
                break

        if not model:
            # Fallback: try to extract from nodeid
            nodeid = test.get("nodeid", "")
            if "-" in nodeid:
                model = nodeid.split("-")[-1].rstrip("]")

        if model and duration > 0:
            model_timings[model].append(duration)

    if not model_timings:
        return ""

    # Build markdown table
    lines = []
    lines.append("## Model Latency Comparison")
    lines.append("")
    lines.append("| Model | Avg (s) | Min (s) | Max (s) | P50 (s) | P95 (s) |")
    lines.append("|-------|---------|---------|---------|---------|---------|")

    for model in sorted(model_timings.keys()):
        timings = sorted(model_timings[model])
        if not timings:
            continue

        avg_time = sum(timings) / len(timings)
        min_time = timings[0]
        max_time = timings[-1]

        # Calculate percentiles
        p50_idx = int(len(timings) * 0.5)
        p95_idx = int(len(timings) * 0.95)
        p50 = timings[p50_idx] if p50_idx < len(timings) else timings[-1]
        p95 = timings[p95_idx] if p95_idx < len(timings) else timings[-1]

        # Format model name for display
        display_model = model.replace("anthropic/", "").replace("-20241022", "")
        if len(display_model) > 30:
            display_model = display_model[:27] + "..."

        lines.append(
            f"| {display_model} | {avg_time:.1f} | {min_time:.1f} | "
            f"{max_time:.1f} | {p50:.1f} | {p95:.1f} |"
        )

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
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract test case from user_properties
        test_case = ""
        for prop in test.get("user_properties", []):
            if isinstance(prop, dict) and "clean_test_case_id" in prop:
                test_case = prop["clean_test_case_id"]
                break

        # Fallback to nodeid parsing
        if not test_case:
            nodeid = test.get("nodeid", "")
            if "[" in nodeid:
                test_case = nodeid.split("[")[1].split("-")[0]

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
    lines.append("### Test Categories")

    for category, tests in categories.items():
        if tests:
            unique_tests = list(set(tests))
            if unique_tests:  # Only add if there are actual test names
                test_list = ", ".join(sorted(unique_tests)[:5])
                if len(unique_tests) > 5:
                    test_list += "..."
                lines.append(
                    f"**{category.title()}** ({len(unique_tests)} tests): {test_list}"
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

    # Model accuracy comparison table
    report_lines.append("## Model Accuracy Comparison")
    report_lines.append("")
    report_lines.append(generate_summary_table(results, models))
    report_lines.append("")

    # Model latency comparison table
    latency_table = generate_latency_comparison_table(results)
    if latency_table:
        report_lines.append(latency_table)
        report_lines.append("")

    # Model by tag performance
    model_tag_table = generate_model_by_tag_table(results)
    if model_tag_table:
        report_lines.append(model_tag_table)
        report_lines.append("")

    # Detailed results
    report_lines.append(generate_detailed_results(results))
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
