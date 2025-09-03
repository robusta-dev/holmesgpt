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
    parser.add_argument(
        "--models",
        help="Comma-separated list of models tested (auto-detected if not provided)",
    )
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


def extract_models_from_results(results: Dict[str, Any]) -> List[str]:
    """Extract unique model names from test results."""
    models = set()

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Try to get model from user_properties
        user_props = test.get("user_properties", [])
        for prop in user_props:
            if isinstance(prop, dict) and "model" in prop:
                models.add(prop["model"])
                break
        else:
            # Fallback to extracting from nodeid
            nodeid = test.get("nodeid", "")
            if "[" in nodeid and "-" in nodeid:
                # Extract model from pattern like [test_case-model]
                params = nodeid.split("[")[1].split("]")[0]
                parts = params.split("-")
                if len(parts) >= 2:
                    model = "-".join(parts[1:])
                    models.add(model)

    return sorted(list(models))


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

        # Use full model name for display
        display_model = model

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


def generate_eval_dashboard_heatmap(results: Dict[str, Any]) -> str:
    """Generate a heatmap dashboard showing each eval x model with color-coded pass rates."""
    # Collect data by eval test and model
    eval_model_stats: DefaultDict[str, DefaultDict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"total": 0, "passed": 0})
    )

    all_evals: Set[str] = set()
    all_models: Set[str] = set()

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract eval test case and model
        eval_case = None
        model = None

        # Try to get from user_properties first
        user_props = test.get("user_properties", [])
        for prop in user_props:
            if isinstance(prop, dict):
                if "clean_test_case_id" in prop:
                    eval_case = prop["clean_test_case_id"]
                if "model" in prop:
                    model = prop["model"]

        # Fallback to nodeid parsing
        if not eval_case or not model:
            nodeid = test.get("nodeid", "")
            if "[" in nodeid and "]" in nodeid:
                params = nodeid.split("[")[1].split("]")[0]
                parts = params.split("-")
                if not eval_case and len(parts) >= 1:
                    eval_case = parts[0]
                if not model and len(parts) >= 2:
                    model = "-".join(parts[1:])

        if eval_case and model:
            all_evals.add(eval_case)
            all_models.add(model)
            outcome = test.get("outcome", "unknown")

            eval_model_stats[eval_case][model]["total"] += 1
            if outcome == "passed":
                eval_model_stats[eval_case][model]["passed"] += 1

    if not all_evals or not all_models:
        return ""

    # Build the dashboard heatmap
    lines = []
    lines.append("## 📊 Evaluation Dashboard")
    lines.append("")
    lines.append(
        "Real-time health status of all evaluations across models. Color coding:"
    )
    lines.append("- 🟢 **Green**: Passing 100% (stable)")
    lines.append("- 🟡 **Yellow**: Passing 50-99% (flaky)")
    lines.append("- 🔴 **Red**: Passing <50% (failing)")
    lines.append("")

    # Sort evals and models
    sorted_evals = sorted(all_evals)
    sorted_models = sorted(all_models)

    # Format model names for display (keep full names)
    display_models = []
    for model in sorted_models:
        display_model = model
        display_models.append(display_model)

    # Create table header
    header = "| Eval ID | " + " | ".join(display_models) + " |"
    separator = "|---------|" + "|".join(["-------"] * len(sorted_models)) + "|"

    lines.append(header)
    lines.append(separator)

    # Data rows (one per eval)
    for eval_case in sorted_evals:
        row = [f"**{eval_case}**"]

        for model in sorted_models:
            stats = eval_model_stats[eval_case][model]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = (passed / total * 100) if total > 0 else 0

                # Determine color and emoji based on pass rate
                if rate == 100:
                    cell = "🟢"  # Perfect pass
                elif rate >= 90:
                    cell = "🟢"  # Very good
                elif rate >= 70:
                    cell = "🟡"  # Flaky
                elif rate >= 50:
                    cell = "🟡"  # More flaky
                elif rate > 0:
                    cell = "🔴"  # Mostly failing
                else:
                    cell = "🔴"  # Complete failure

                # Add hover text with details (for markdown that supports it)
                cell = f"{cell}"
            else:
                cell = "⬜"  # No data

            row.append(cell)

        lines.append("| " + " | ".join(row) + " |")

    # Add summary row (no separator needed in markdown tables)
    summary_row = ["**SUMMARY**"]

    for model in sorted_models:
        total_passed = 0
        total_tests = 0
        for eval_case in sorted_evals:
            stats = eval_model_stats[eval_case][model]
            total_passed += stats["passed"]
            total_tests += stats["total"]

        if total_tests > 0:
            overall_rate = total_passed / total_tests * 100
            if overall_rate >= 95:
                cell = f"🟢 {overall_rate:.0f}%"
            elif overall_rate >= 80:
                cell = f"🟡 {overall_rate:.0f}%"
            else:
                cell = f"🔴 {overall_rate:.0f}%"
        else:
            cell = "N/A"

        summary_row.append(cell)

    lines.append("| " + " | ".join(summary_row) + " |")

    # Add detailed breakdown for reference
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>📈 Click for detailed pass rates</summary>")
    lines.append("")
    lines.append("| Eval ID | " + " | ".join(display_models) + " |")
    lines.append("|---------|" + "|".join(["-------"] * len(sorted_models)) + "|")

    for eval_case in sorted_evals:
        row = [f"{eval_case}"]

        for model in sorted_models:
            stats = eval_model_stats[eval_case][model]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = (passed / total * 100) if total > 0 else 0
                cell = f"{rate:.0f}% ({passed}/{total})"
            else:
                cell = "-"

            row.append(cell)

        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("</details>")

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

    # Use full model names for display
    display_models = []
    for model in sorted_models:
        display_model = model
        display_models.append(display_model)

    header = "| Tag | " + " | ".join(display_models) + " |"
    separator = "|-----|" + "|".join(["-------"] * len(sorted_models)) + "|"

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

        # Use full model name for display
        display_model = model

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

    # Parse models - auto-detect from results if not provided
    if args.models:
        models = args.models.split(",")
    else:
        models = extract_models_from_results(results)
        if models:
            print(f"Auto-detected models: {', '.join(models)}")

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

    # Dashboard heatmap - show this first for quick overview
    dashboard = generate_eval_dashboard_heatmap(results)
    if dashboard:
        report_lines.append(dashboard)
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
