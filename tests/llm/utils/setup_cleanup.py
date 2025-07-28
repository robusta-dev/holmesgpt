"""Setup and cleanup infrastructure for test cases."""

import logging
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from strenum import StrEnum

from tests.llm.utils.commands import run_commands  # type: ignore[attr-defined]
from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]
from tests.llm.utils.test_helpers import truncate_output

# Configuration
MAX_ERROR_LINES = 10
MAX_WORKERS = 30


def log(msg):
    """Force a log to be written even with xdist, which captures stdout. (must use -s to see this)"""
    sys.stderr.write(msg)
    sys.stderr.write("\n")
    # we also log to stderr so its visible when xdist is not used
    logging.info(msg)


def format_error_output(error_details: str) -> str:
    """Format error details with truncation if needed."""
    return truncate_output(error_details, max_lines=MAX_ERROR_LINES)


class Operation(StrEnum):
    """Enum for operation types."""

    SETUP = "Setup"
    CLEANUP = "Cleanup"


def run_all_test_commands(
    test_cases: List[HolmesTestCase], operation: Operation
) -> Dict[str, str]:
    """Run before_test/after_test (according to operation)

    Args:
        test_cases: List of test cases to process
        command_func: Function to call for each test case (before_test or after_test)
        operation_name: Name of operation for logging ("Setup" or "Cleanup")

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
                    run_commands, test_case, test_case.before_test, operation_lower
                ): test_case
                for test_case in test_cases
            }
        else:
            future_to_test_case = {
                executor.submit(
                    run_commands, test_case, test_case.after_test, operation_lower
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

                    # Store failure info for setup
                    if operation == Operation.SETUP:
                        failed_setup_info[test_case.id] = (
                            f"Setup timeout: Command timed out after {result.elapsed_time:.2f}s"
                        )

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

                    # Store failure info for setup
                    if operation == Operation.SETUP:
                        failed_setup_info[test_case.id] = (
                            f"Setup failed: Command failed with {result.exit_info}"
                        )

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


def run_all_test_setup(test_cases: List[HolmesTestCase]) -> Dict[str, str]:
    """Run before_test for each test case in parallel.

    Returns:
        Dict[str, str]: Mapping of test_case.id to error message for failed setups
    """
    return run_all_test_commands(test_cases, Operation.SETUP)


def run_all_test_cleanup(test_cases: List[HolmesTestCase]) -> None:
    """Run after_test for each test case in parallel."""
    run_all_test_commands(test_cases, Operation.CLEANUP)


def extract_test_cases_needing_setup(session) -> List[HolmesTestCase]:
    """Extract unique test cases that need setup from session items."""
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
                and test_case.before_test
                and test_case.id not in seen_ids
                and not test_case.skip  # Don't run setup for skipped tests
            ):
                test_cases.append(test_case)
                seen_ids.add(test_case.id)

    return test_cases
