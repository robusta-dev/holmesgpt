#!/usr/bin/env python3
"""Generate markdown report from eval results."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, DefaultDict, Set, Optional
from collections import defaultdict
from urllib.parse import quote

# Global Braintrust configuration
BRAINTRUST_ORG = os.environ.get("BRAINTRUST_ORG", "robustadev")
BRAINTRUST_PROJECT = os.environ.get("BRAINTRUST_PROJECT", "HolmesGPT")


def strip_provider_prefix(model_name: str) -> str:
    """Strip common provider prefixes from model names for cleaner display.

    Args:
        model_name: Full model name potentially with provider prefix

    Returns:
        Model name with provider prefix removed
    """
    for prefix in ["anthropic/", "openai/", "azure/", "bedrock/", "vertex_ai/"]:
        if model_name.startswith(prefix):
            return model_name[len(prefix) :]
    return model_name


def get_rate_emoji(rate: float) -> str:
    """Get emoji indicator based on success rate.

    Args:
        rate: Success rate percentage (0-100)

    Returns:
        Emoji string: 🟢 for 100%, 🔴 for 0%, 🟡 for anything in between
    """
    if rate == 100:
        return "🟢"
    elif rate == 0:
        return "🔴"
    else:
        return "🟡"


def extract_experiment_name_from_results(results: Dict[str, Any]) -> Optional[str]:
    """Extract experiment name from test results if available.

    Args:
        results: Test results dictionary

    Returns:
        Experiment name string, or None if not found
    """
    for test in results.get("tests", []):
        user_props = test.get("user_properties", [])
        for prop in user_props:
            if isinstance(prop, dict) and "braintrust_experiment" in prop:
                return prop["braintrust_experiment"]
    return None


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


def get_braintrust_url(test_data: Dict[str, Any]) -> Optional[str]:
    """Generate Braintrust URL for a test if span IDs are available.

    Args:
        test_data: Test result dictionary that may contain user_properties

    Returns:
        Braintrust URL string, or None if span IDs not available
    """
    # Check if Braintrust is configured
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return None

    # Extract span IDs and experiment name from user_properties
    user_props = test_data.get("user_properties", [])
    span_id = None
    root_span_id = None
    experiment_name = None

    for prop in user_props:
        if isinstance(prop, dict):
            if "braintrust_span_id" in prop:
                span_id = prop["braintrust_span_id"]
            if "braintrust_root_span_id" in prop:
                root_span_id = prop["braintrust_root_span_id"]
            if "braintrust_experiment" in prop:
                experiment_name = prop["braintrust_experiment"]

    if not span_id or not root_span_id:
        return None

    # Use global Braintrust config

    # Use stored experiment name, or fall back to generating it
    if not experiment_name:
        branch = os.environ.get(
            "GITHUB_REF_NAME", os.environ.get("BUILDKITE_BRANCH", "unknown")
        )
        experiment_name = os.environ.get("EXPERIMENT_ID", f"holmes-benchmark-{branch}")

    # URL encode the experiment name
    encoded_experiment_name = quote(experiment_name, safe="")

    # Build URL with span IDs
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}?c=&r={span_id}&s={root_span_id}"

    return url


def get_braintrust_filter_url(
    eval_case: str, model: str, experiment_name: Optional[str] = None
) -> Optional[str]:
    """Generate Braintrust URL with search filter for a specific eval/model combination.

    Args:
        eval_case: The test case ID (e.g., "01_how_many_pods")
        model: The model name (e.g., "gpt-4o")
        experiment_name: Optional experiment name, will be auto-detected if not provided

    Returns:
        Braintrust URL string with search filter, or None if Braintrust not configured
    """
    # Check if Braintrust is configured
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return None

    # Use global Braintrust config

    # Use provided experiment name or fall back to generating it
    if not experiment_name:
        branch = os.environ.get(
            "GITHUB_REF_NAME", os.environ.get("BUILDKITE_BRANCH", "unknown")
        )
        experiment_name = os.environ.get("EXPERIMENT_ID", f"holmes-benchmark-{branch}")

    # URL encode the experiment name
    encoded_experiment_name = quote(experiment_name, safe="")

    # Create the filter string for span_attributes.name
    # The name format in Braintrust is typically: "test_case[model]"
    span_name = f"{eval_case}[{model}]"

    # Build the filter JSON structure
    filter_obj = {
        "filter": [
            {
                "text": f'span_attributes.name = "{span_name}"',
                "label": f"Name equals {span_name}",
                "originType": "form",
            }
        ]
    }

    # URL encode the filter (double encoding for the nested structure)
    # First encode the inner text field
    filter_obj["filter"][0]["text"] = quote(filter_obj["filter"][0]["text"], safe="")
    filter_obj["filter"][0]["label"] = quote(filter_obj["filter"][0]["label"], safe="")

    # Then encode the whole JSON
    filter_json = json.dumps(filter_obj)
    encoded_filter = quote(filter_json, safe="")

    # Build URL with search filter
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}?c=&search={encoded_filter}"

    return url


def get_braintrust_tag_filter_url(
    tag: str, experiment_name: Optional[str] = None
) -> Optional[str]:
    """Generate Braintrust URL with search filter for all tests with a specific tag.

    Args:
        tag: The tag name (e.g., "logs", "easy")
        experiment_name: Optional experiment name, will be auto-detected if not provided

    Returns:
        Braintrust URL string with search filter, or None if Braintrust not configured
    """
    # Check if Braintrust is configured
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return None

    # Use global Braintrust config

    # Use provided experiment name or fall back to generating it
    if not experiment_name:
        branch = os.environ.get(
            "GITHUB_REF_NAME", os.environ.get("BUILDKITE_BRANCH", "unknown")
        )
        experiment_name = os.environ.get("EXPERIMENT_ID", f"holmes-benchmark-{branch}")

    # URL encode the experiment name
    encoded_experiment_name = quote(experiment_name, safe="")

    # Build the filter JSON structure for tags
    import json

    filter_obj = {
        "filter": [
            {
                "text": f'tags includes ["{tag}"]',
                "label": f"Tags includes {tag}",
                "originType": "form",
            }
        ]
    }

    # URL encode the filter (double encoding for the nested structure)
    # First encode the inner text field
    filter_obj["filter"][0]["text"] = quote(filter_obj["filter"][0]["text"], safe="")
    filter_obj["filter"][0]["label"] = quote(filter_obj["filter"][0]["label"], safe="")

    # Then encode the whole JSON
    filter_json = json.dumps(filter_obj)
    encoded_filter = quote(filter_json, safe="")

    # Build URL with search filter
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}?c=&search={encoded_filter}"

    return url


def get_braintrust_eval_filter_url(
    eval_id: str, experiment_name: Optional[str] = None
) -> Optional[str]:
    """Generate Braintrust URL with search filter for all tests of a specific eval.

    Args:
        eval_id: The eval/test case ID (e.g., "01_how_many_pods")
        experiment_name: Optional experiment name, will be auto-detected if not provided

    Returns:
        Braintrust URL string with search filter, or None if Braintrust not configured
    """
    # Check if Braintrust is configured
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return None

    # Use global Braintrust config

    # Use provided experiment name or fall back to generating it
    if not experiment_name:
        branch = os.environ.get(
            "GITHUB_REF_NAME", os.environ.get("BUILDKITE_BRANCH", "unknown")
        )
        experiment_name = os.environ.get("EXPERIMENT_ID", f"holmes-benchmark-{branch}")

    # URL encode the experiment name
    encoded_experiment_name = quote(experiment_name, safe="")

    # Build the filter JSON structure for metadata.eval_id
    filter_obj = {
        "filter": [
            {
                "text": f'metadata.eval_id = "{eval_id}"',
                "label": f"metadata.eval_id equals {eval_id}",
                "originType": "form",
            }
        ]
    }

    # URL encode the filter (double encoding for the nested structure)
    # First encode the inner text field
    filter_obj["filter"][0]["text"] = quote(filter_obj["filter"][0]["text"], safe="")
    filter_obj["filter"][0]["label"] = quote(filter_obj["filter"][0]["label"], safe="")

    # Then encode the whole JSON
    filter_json = json.dumps(filter_obj)
    encoded_filter = quote(filter_json, safe="")

    # Build URL with search filter
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}?c=&search={encoded_filter}"

    return url


def get_braintrust_model_filter_url(
    model: str, experiment_name: Optional[str] = None
) -> Optional[str]:
    """Generate Braintrust URL with search filter for all tests of a specific model.

    Args:
        model: The model name (e.g., "gpt-4o")
        experiment_name: Optional experiment name, will be auto-detected if not provided

    Returns:
        Braintrust URL string with search filter, or None if Braintrust not configured
    """
    # Check if Braintrust is configured
    if not os.environ.get("BRAINTRUST_API_KEY"):
        return None

    # Use global Braintrust config

    # Use provided experiment name or fall back to generating it
    if not experiment_name:
        branch = os.environ.get(
            "GITHUB_REF_NAME", os.environ.get("BUILDKITE_BRANCH", "unknown")
        )
        experiment_name = os.environ.get("EXPERIMENT_ID", f"holmes-benchmark-{branch}")

    # URL encode the experiment name
    encoded_experiment_name = quote(experiment_name, safe="")

    # Build the filter JSON structure for metadata.model
    import json

    filter_obj = {
        "filter": [
            {
                "text": f'metadata.model = "{model}"',
                "label": f"metadata.model equals {model}",
                "originType": "form",
            }
        ]
    }

    # URL encode the filter (double encoding for the nested structure)
    # First encode the inner text field
    filter_obj["filter"][0]["text"] = quote(filter_obj["filter"][0]["text"], safe="")
    filter_obj["filter"][0]["label"] = quote(filter_obj["filter"][0]["label"], safe="")

    # Then encode the whole JSON
    filter_json = json.dumps(filter_obj)
    encoded_filter = quote(filter_json, safe="")

    # Build URL with search filter
    url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}?c=&search={encoded_filter}"

    return url


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

        # Strip provider prefix for cleaner display
        display_model = strip_provider_prefix(model)

        # Add emoji indicator based on success rate
        indicator = get_rate_emoji(success_rate)

        lines.append(
            f"| {display_model} | {passed} | {failed} | {skipped} | {total} | "
            f"{indicator} {success_rate:.1f}% |"
        )

    return "\n".join(lines)


def generate_eval_dashboard_heatmap(results: Dict[str, Any]) -> str:
    """Generate a heatmap dashboard showing each eval x model with color-coded pass rates."""
    # Collect data by eval test and model, including test references for Braintrust links
    eval_model_stats: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "total": 0,
                "passed": 0,
                "tests": [],
                "total_duration": 0,
                "total_cost": 0,
            }
        )
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

            # Add duration if available
            duration = (
                test.get("call", {}).get("duration", 0) if test.get("call") else 0
            )
            if duration > 0:
                eval_model_stats[eval_case][model]["total_duration"] += duration

            # Add cost if available (from user_properties)
            cost = 0
            for prop in user_props:
                if isinstance(prop, dict) and "cost" in prop:
                    cost = prop["cost"]
                    break
            if cost > 0:
                eval_model_stats[eval_case][model]["total_cost"] += cost

            # Store the test data for potential Braintrust link
            eval_model_stats[eval_case][model]["tests"].append(test)

    if not all_evals or not all_models:
        return ""

    # Build the dashboard heatmap
    lines = []
    lines.append("## 📊 Evaluation Dashboard")
    lines.append("")
    lines.append("Status of all evaluations across models. Color coding:")
    lines.append("- 🟢 **Green**: Passing 100% (stable)")
    lines.append("- 🟡 **Yellow**: Passing 1-99%")
    lines.append("- 🔴 **Red**: Passing 0% (failing)")
    lines.append("")

    # Sort evals and models
    sorted_evals = sorted(all_evals)
    sorted_models = sorted(all_models)

    # Extract experiment name from any test that has it (needed for URLs)
    # We need to extract from the actual test data stored in eval_model_stats
    experiment_name = None
    for eval_case in sorted_evals:
        for model in sorted_models:
            stats = eval_model_stats[eval_case][model]
            if stats.get("tests"):
                for test in stats["tests"]:
                    user_props = test.get("user_properties", [])
                    for prop in user_props:
                        if isinstance(prop, dict) and "braintrust_experiment" in prop:
                            experiment_name = prop["braintrust_experiment"]
                            break
                    if experiment_name:
                        break
            if experiment_name:
                break
        if experiment_name:
            break

    # Format model names for display (strip provider prefix) and create links
    display_model_headers = []
    for model in sorted_models:
        # Strip common provider prefixes for cleaner display
        display_model = strip_provider_prefix(model)

        # Create link to filter by this model
        model_filter_url = get_braintrust_model_filter_url(model, experiment_name)
        if model_filter_url:
            display_model_headers.append(f"[{display_model}]({model_filter_url})")
        else:
            display_model_headers.append(display_model)

    # Create table header
    header = "| Eval ID | " + " | ".join(display_model_headers) + " |"
    separator = "|---------|" + "|".join(["-------"] * len(sorted_models)) + "|"

    lines.append(header)
    lines.append(separator)

    # Data rows (one per eval)
    for eval_case in sorted_evals:
        # Create link for the eval ID
        eval_filter_url = get_braintrust_eval_filter_url(eval_case, experiment_name)
        if eval_filter_url:
            row = [f"[**{eval_case}**]({eval_filter_url})"]
        else:
            row = [f"**{eval_case}**"]

        for model in sorted_models:
            stats = eval_model_stats[eval_case][model]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = (passed / total * 100) if total > 0 else 0

                # Get Braintrust filter URL for this eval/model combination
                braintrust_url = get_braintrust_filter_url(
                    eval_case, model, experiment_name
                )

                # Determine color and emoji based on pass rate
                emoji = get_rate_emoji(rate)

                # Create cell with link if available
                if braintrust_url:
                    cell = f"[{emoji}]({braintrust_url})"
                else:
                    cell = emoji
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

            # Get model filter URL
            model_filter_url = get_braintrust_model_filter_url(model, experiment_name)

            # Create summary text with emoji
            emoji = get_rate_emoji(overall_rate)
            summary_text = f"{emoji} {overall_rate:.0f}%"

            # Add link if available
            if model_filter_url:
                cell = f"[{summary_text}]({model_filter_url})"
            else:
                cell = summary_text
        else:
            cell = "N/A"

        summary_row.append(cell)

    lines.append("| " + " | ".join(summary_row) + " |")

    # Add detailed breakdown for reference
    lines.append("")
    lines.append("<details>")
    lines.append(
        "<summary>📈 Click for detailed pass rates, timings, and costs</summary>"
    )
    lines.append("")
    # Create display model names for the detailed table
    display_models_detail = []
    for model in sorted_models:
        display_model = strip_provider_prefix(model)
        display_models_detail.append(display_model)

    lines.append("| Eval ID | " + " | ".join(display_models_detail) + " |")
    lines.append("|---------|" + "|".join(["-------"] * len(sorted_models)) + "|")

    for eval_case in sorted_evals:
        # Create link for the eval ID in detailed breakdown
        eval_filter_url = get_braintrust_eval_filter_url(eval_case, experiment_name)
        if eval_filter_url:
            row = [f"[{eval_case}]({eval_filter_url})"]
        else:
            row = [f"{eval_case}"]

        for model in sorted_models:
            stats = eval_model_stats[eval_case][model]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = (passed / total * 100) if total > 0 else 0

                # Calculate average duration and cost if available
                avg_duration = (
                    stats["total_duration"] / stats["total"]
                    if stats["total_duration"] > 0
                    else 0
                )
                avg_cost = (
                    stats["total_cost"] / stats["total"]
                    if stats.get("total_cost", 0) > 0
                    else 0
                )

                # Get Braintrust filter URL for this eval/model combination
                braintrust_url = get_braintrust_filter_url(
                    eval_case, model, experiment_name
                )

                # Determine emoji based on pass rate
                emoji = get_rate_emoji(rate)

                # Create multi-line cell with accuracy, time, and cost on separate lines
                cell_parts = [f"{emoji} {rate:.0f}% ({passed}/{total})"]
                if avg_duration > 0:
                    cell_parts.append(f"⏱️ {avg_duration:.1f}s")
                if avg_cost > 0:
                    cell_parts.append(f"💰 ${avg_cost:.4f}")

                cell_text = "<br>".join(cell_parts)

                if braintrust_url:
                    # For multi-line links, we need to wrap the whole thing
                    cell = f"[{cell_text}]({braintrust_url})"
                else:
                    cell = cell_text
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

    # Extract experiment name from any test that has it (needed for URLs)
    experiment_name = extract_experiment_name_from_results(results)

    # Build the table with tags as rows and models as columns
    lines = []
    lines.append("## Performance by Tag")
    lines.append("")
    lines.append("Success rate by test category and model:")
    lines.append("")

    # Header with models as columns
    sorted_models = sorted(all_models)
    sorted_tags = sorted(all_tags)

    # Strip provider prefixes for cleaner display
    display_models = []
    for model in sorted_models:
        display_model = strip_provider_prefix(model)
        display_models.append(display_model)

    header = "| Tag | " + " | ".join(display_models) + " |"
    separator = "|-----|" + "|".join(["-------"] * len(sorted_models)) + "|"

    lines.append(header)
    lines.append(separator)

    # Data rows (one per tag)
    for tag in sorted_tags:
        # Create tag link if available
        tag_filter_url = get_braintrust_tag_filter_url(tag, experiment_name)
        if tag_filter_url:
            row = [f"[{tag}]({tag_filter_url})"]
        else:
            row = [tag]

        for model in sorted_models:
            stats = model_tag_stats[model][tag]
            if stats["total"] > 0:
                passed = stats["passed"]
                total = stats["total"]
                rate = passed / total * 100
                # Add emoji based on rate
                emoji = get_rate_emoji(rate)
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
            emoji = get_rate_emoji(overall_rate)
            overall_row.append(
                f"{emoji} {overall_rate:.0f}% ({total_passed}/{total_tests})"
            )
        else:
            overall_row.append("N/A")

    lines.append("| " + " | ".join(overall_row) + " |")

    return "\n".join(lines)


def generate_cost_comparison_table(results: Dict[str, Any]) -> str:
    """Generate model cost comparison table."""
    model_costs: DefaultDict[str, List[float]] = defaultdict(list)

    for test in results.get("tests", []):
        # Skip deselected tests
        if test.get("outcome") == "deselected":
            continue

        # Extract model and cost from user_properties
        model = None
        cost = None

        user_props = test.get("user_properties", [])
        for prop in user_props:
            if isinstance(prop, dict):
                if "model" in prop:
                    model = prop["model"]
                if "cost" in prop:
                    cost = prop["cost"]

        # Fallback: try to extract model from nodeid if needed
        if not model:
            nodeid = test.get("nodeid", "")
            if "-" in nodeid:
                model = nodeid.split("-")[-1].rstrip("]")

        if model and cost is not None and cost > 0:
            model_costs[model].append(cost)

    if not model_costs:
        return ""

    # Build markdown table
    lines = []
    lines.append("## Model Cost Comparison")
    lines.append("")
    lines.append("| Model | Avg Cost | Min Cost | Max Cost | Total Cost | Tests |")
    lines.append("|-------|----------|----------|----------|------------|-------|")

    for model in sorted(model_costs.keys()):
        costs = model_costs[model]
        if not costs:
            continue

        avg_cost = sum(costs) / len(costs)
        min_cost = min(costs)
        max_cost = max(costs)
        total_cost = sum(costs)
        num_tests = len(costs)

        # Strip provider prefix for cleaner display
        display_model = strip_provider_prefix(model)

        lines.append(
            f"| {display_model} | ${avg_cost:.4f} | ${min_cost:.4f} | "
            f"${max_cost:.4f} | ${total_cost:.2f} | {num_tests} |"
        )

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

        # Strip provider prefix for cleaner display
        display_model = strip_provider_prefix(model)

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

    # About this benchmark
    report_lines.append("## About this Benchmark")
    report_lines.append("")
    report_lines.append(
        "HolmesGPT is continuously evaluated against 100+ real-world "
        "Kubernetes and cloud troubleshooting scenarios."
    )
    report_lines.append("")
    report_lines.append(
        "If you find scenarios that HolmesGPT does not perform "
        "well on, please consider adding them as evals to the benchmark."
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

    # Model cost comparison table
    cost_table = generate_cost_comparison_table(results)
    if cost_table:
        report_lines.append(cost_table)
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

    # Footer
    report_lines.append("---")

    # Try to get experiment URL from any test that has Braintrust data
    experiment_url = None
    experiment_name = extract_experiment_name_from_results(results)

    if experiment_name:
        # Build experiment URL without span IDs (just the experiment page)
        encoded_experiment_name = quote(experiment_name, safe="")
        experiment_url = f"https://www.braintrust.dev/app/{BRAINTRUST_ORG}/p/{BRAINTRUST_PROJECT}/experiments/{encoded_experiment_name}"

    # Generate footer text with specific experiment link if available
    if experiment_url and experiment_name:
        report_lines.append(
            f"*Results are automatically generated and updated weekly. "
            f"View full traces and detailed analysis in [Braintrust experiment: {experiment_name}]({experiment_url}).*"
        )
    else:
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
