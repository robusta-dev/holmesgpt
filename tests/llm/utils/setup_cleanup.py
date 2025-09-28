"""Setup and cleanup infrastructure for test cases."""

import logging
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from strenum import StrEnum

from tests.llm.utils.commands import run_commands  # type: ignore[attr-defined]
from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]
from pathlib import Path

# Configuration
MAX_ERROR_LINES = 10
MAX_WORKERS = 30


def log(msg):
    """Force a log to be written even with xdist, which captures stdout. (must use -s to see this)"""
    if os.environ.get("PYTEST_XDIST_WORKER"):
        # If running under xdist, we log to stderr so it appears in the pytest output
        # This is necessary because xdist captures stdout and doesn't show it in the output
        sys.stderr.write(msg)
        sys.stderr.write("\n")
    else:
        # If not running under xdist, we log to stdout
        logging.info(msg)


def _truncate_output(data: str, max_lines: int = 10, label: str = "lines") -> str:
    """Truncate output to max_lines for readability."""
    lines = data.split("\n")
    if len(lines) > max_lines:
        preview_lines = lines[:max_lines]
        remaining = len(lines) - max_lines
        preview_lines.append(f"... [TRUNCATED: {remaining} more {label} not shown]")
        return "\n".join(preview_lines)
    return data


def format_error_output(error_details: str) -> str:
    """Format error details with truncation if needed."""
    return _truncate_output(error_details, max_lines=MAX_ERROR_LINES)


class Operation(StrEnum):
    """Enum for operation types."""

    SETUP = "Setup"
    CLEANUP = "Cleanup"


def get_prometheus_alert_commands(
    test_case: HolmesTestCase,
    operation: Operation,
    create_alerts: bool,
    prometheus_label: str,
) -> str:
    """Generate commands for deploying/cleaning up Prometheus alerts.

    Args:
        test_case: The test case configuration
        operation: Whether this is setup or cleanup
        create_alerts: Whether to create Prometheus alerts (from pytest flag)
        prometheus_label: Prometheus label override (from pytest flag)

    Returns:
        Shell commands to handle Prometheus alerts, or empty string if not needed
    """
    if not test_case.prometheus_alert:
        return ""

    if not create_alerts:
        return ""

    alert_file = Path(test_case.folder) / test_case.prometheus_alert
    if not alert_file.exists():
        return ""

    if operation == Operation.SETUP:
        # Deploy alert
        if prometheus_label:
            return f'sed "s/release: robusta/release: {prometheus_label}/" {test_case.prometheus_alert} | kubectl apply -f -'
        else:
            return f"kubectl apply -f {test_case.prometheus_alert}"
    else:
        # Cleanup alert
        if prometheus_label:
            return f'sed "s/release: robusta/release: {prometheus_label}/" {test_case.prometheus_alert} | kubectl delete -f - || true'
        else:
            return f"kubectl delete -f {test_case.prometheus_alert} || true"


def run_all_test_commands(
    test_cases: List[HolmesTestCase],
    operation: Operation,
    create_alerts: bool = False,
    prometheus_label: str = "",
) -> Dict[str, str]:
    """Run before_test/after_test (according to operation)

    Args:
        test_cases: List of test cases to process
        operation: Operation type (Setup or Cleanup)
        create_alerts: Whether to create Prometheus alerts (from pytest flag)
        prometheus_label: Prometheus label override (from pytest flag)

    Returns:
        Dict[str, str]: Mapping of test_case.id to error message for failed setups
    """
    operation_lower = operation.value.lower()
    operation_plural = f"{operation_lower}s"

    log(
        f"\n⚙️ {'Running before_test' if operation == Operation.SETUP else 'Running after_test'} for {len(test_cases)} unique evals: {', '.join(tc.id for tc in test_cases)}"
    )

    start_time = time.time()
    successful_test_cases = 0
    failed_test_cases = 0
    timed_out_test_cases = 0
    failed_setup_info = {}  # Map test_case.id to error message

    with ThreadPoolExecutor(max_workers=min(len(test_cases), MAX_WORKERS)) as executor:
        if operation == Operation.SETUP:
            future_to_test_case = {
                executor.submit(
                    run_commands,
                    test_case,
                    (test_case.before_test or "")
                    + get_prometheus_alert_commands(
                        test_case, operation, create_alerts, prometheus_label
                    ),
                    operation_lower,
                ): test_case
                for test_case in test_cases
            }
        else:
            future_to_test_case = {
                executor.submit(
                    run_commands,
                    test_case,
                    get_prometheus_alert_commands(
                        test_case, operation, create_alerts, prometheus_label
                    )
                    + (test_case.after_test or ""),
                    operation_lower,
                ): test_case
                for test_case in test_cases
            }

        # Wait for all tasks to complete and handle results
        for future in as_completed(future_to_test_case):
            test_case = future_to_test_case[future]
            try:
                result = future.result()  # Single CommandResult for the test case
                remaining_cases = (
                    len(test_cases)
                    - successful_test_cases
                    - failed_test_cases
                    - timed_out_test_cases
                ) - 1  # Subtract 1 for the current test case
                if result.success:
                    successful_test_cases += 1
                    log(
                        f"✅ {operation.value} {test_case.id}: {result.command} ({result.elapsed_time:.2f}s); {operation_plural} remaining: {remaining_cases}"
                    )
                elif result.error_type == "timeout":
                    timed_out_test_cases += 1
                    log(
                        f"⏰ {operation.value} {test_case.id}: TIMEOUT after {result.elapsed_time:.2f}s; {operation_plural} remaining: {remaining_cases}"
                    )

                    # Show the exact command that timed out
                    # truncated_error = format_error_output(result.error_details)
                    # log(textwrap.indent(truncated_error, "   "))
                    # log(
                    #    f"[{test_case.id}] {operation.value} timeout: {result.error_details}"
                    # )

                    # Store failure info for setup with detailed information
                    if operation == Operation.SETUP:
                        # Store the full error details without truncation for Braintrust
                        failed_setup_info[test_case.id] = result.error_details

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"{operation.value} timeout for test {test_case.id}: Command '{result.command}' timed out after {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )
                else:
                    failed_test_cases += 1
                    log(
                        f"\n❌ {operation.value} {test_case.id}: FAILED ({result.exit_info}, {result.elapsed_time:.2f}s); {operation_plural} remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    # truncated_error = format_error_output(result.error_details)
                    # log(textwrap.indent(truncated_error, "   "))
                    # log(
                    #    f"[{test_case.id}] {operation.value} failed: {result.error_details}"
                    # )

                    # Store failure info for setup with detailed information
                    if operation == Operation.SETUP:
                        # Store the full error details without truncation for Braintrust
                        # This includes the script, exit code, stdout, and stderr
                        failed_setup_info[test_case.id] = result.error_details

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"{operation.value} failed for test {test_case.id}: Command '{result.command}' failed with {result.exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )

            except Exception as e:
                failed_test_cases += 1
                log(f"❌ {operation.value} {test_case.id}: EXCEPTION - {e}")

                # Store failure info for setup
                if operation == Operation.SETUP:
                    failed_setup_info[test_case.id] = f"Setup exception: {str(e)}"

                # Emit warning to make it visible in pytest output
                warnings.warn(
                    f"{operation.value} exception for test {test_case.id}: {str(e)}",
                    UserWarning,
                    stacklevel=2,
                )

    elapsed_time = time.time() - start_time
    log(
        f"⚙️ {operation.value} completed in {elapsed_time:.2f}s: {successful_test_cases} successful, {failed_test_cases} failed, {timed_out_test_cases} timeout"
    )

    return failed_setup_info


def run_all_test_setup(
    test_cases: List[HolmesTestCase],
    create_alerts: bool = False,
    prometheus_label: str = "",
) -> Dict[str, str]:
    """Run before_test for each test case in parallel.

    Args:
        test_cases: List of test cases to process
        create_alerts: Whether to create Prometheus alerts (from pytest flag)
        prometheus_label: Prometheus label override (from pytest flag)

    Returns:
        Dict[str, str]: Mapping of test_case.id to error message for failed setups
    """
    # Run the before_test commands (which create namespaces, deployments, etc.)
    setup_failures = run_all_test_commands(
        test_cases, Operation.SETUP, create_alerts, prometheus_label
    )

    return setup_failures


def run_all_test_cleanup(
    test_cases: List[HolmesTestCase],
    create_alerts: bool = False,
    prometheus_label: str = "",
) -> None:
    """Run after_test for each test case in parallel.

    Args:
        test_cases: List of test cases to process
        create_alerts: Whether to create Prometheus alerts (from pytest flag)
        prometheus_label: Prometheus label override (from pytest flag)
    """
    # Run the after_test commands
    run_all_test_commands(
        test_cases, Operation.CLEANUP, create_alerts, prometheus_label
    )


def extract_llm_test_cases(session) -> List[HolmesTestCase]:
    """Extract unique LLM test cases from session items.

    Args:
        session: pytest session object

    Returns:
        List of unique HolmesTestCase instances (excluding skipped tests)
    """
    seen_ids = set()
    test_cases = []

    for item in session.items:
        if (
            item.get_closest_marker("llm")
            and hasattr(item, "callspec")
            and "test_case" in item.callspec.params
        ):
            test_case = item.callspec.params["test_case"]
            if (
                isinstance(test_case, HolmesTestCase)
                and test_case.id not in seen_ids
                and not test_case.skip  # Don't include skipped tests
            ):
                test_cases.append(test_case)
                seen_ids.add(test_case.id)

    return test_cases
