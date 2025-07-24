"""Setup and cleanup infrastructure for test cases."""

import logging
import textwrap
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from tests.llm.utils.commands import before_test, after_test  # type: ignore[attr-defined]
from tests.llm.utils.test_case_utils import HolmesTestCase  # type: ignore[attr-defined]
from tests.llm.utils.test_helpers import truncate_output

# Configuration
MAX_ERROR_LINES = 10
MAX_WORKERS = 30


def format_error_output(error_details: str) -> str:
    """Format error details with truncation if needed."""
    return truncate_output(error_details, max_lines=MAX_ERROR_LINES)


def run_test_commands(test_cases, command_func, operation_name):
    """Generic function to run test commands (setup/cleanup) in parallel.

    Args:
        test_cases: List of test cases to process
        command_func: Function to call for each test case (before_test or after_test)
        operation_name: Name of operation for logging ("Setup" or "Cleanup")
    """
    operation_lower = operation_name.lower()
    operation_plural = f"{operation_lower}s"

    print(
        f"{'Setting up' if operation_name == 'Setup' else 'Cleaning up'} infrastructure {'for' if operation_name == 'Setup' else 'after tests for'} {len(test_cases)} test cases"
    )

    start_time = time.time()
    successful_test_cases = 0
    failed_test_cases = 0
    timed_out_test_cases = 0

    with ThreadPoolExecutor(max_workers=min(len(test_cases), MAX_WORKERS)) as executor:
        # Submit all tasks
        future_to_test_case = {
            executor.submit(command_func, test_case): test_case
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
                )
                if result.success:
                    successful_test_cases += 1
                    print(
                        f"✅ {operation_name} {test_case.id}: {result.command} ({result.elapsed_time:.2f}s); {operation_plural} remaining: {remaining_cases}"
                    )
                elif result.error_type == "timeout":
                    timed_out_test_cases += 1
                    print(
                        f"⏰ {operation_name} {test_case.id}: TIMEOUT after {result.elapsed_time:.2f}s; {operation_plural} remaining: {remaining_cases}"
                    )

                    # Show the exact command that timed out
                    truncated_error = format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] {operation_name} timeout: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"{operation_name} timeout for test {test_case.id}: Command '{result.command}' timed out after {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )
                else:
                    failed_test_cases += 1
                    print(
                        f"❌ {operation_name} {test_case.id}: FAILED ({result.exit_info}, {result.elapsed_time:.2f}s); {operation_plural} remaining: {remaining_cases}"
                    )

                    # Limit error details to 10 lines and add proper formatting
                    truncated_error = format_error_output(result.error_details)
                    print(textwrap.indent(truncated_error, "   "))
                    logging.error(
                        f"[{test_case.id}] {operation_name} failed: {result.error_details}"
                    )

                    # Emit warning to make it visible in pytest output
                    warnings.warn(
                        f"{operation_name} failed for test {test_case.id}: Command '{result.command}' failed with {result.exit_info} in {result.elapsed_time:.2f}s. Output: {result.error_details}",
                        UserWarning,
                        stacklevel=2,
                    )

            except Exception as e:
                failed_test_cases += 1
                print(f"❌ {operation_name} {test_case.id}: EXCEPTION - {e}")
                logging.error(
                    f"{operation_name} exception for {test_case.id}: {str(e)}"
                )

                # Emit warning to make it visible in pytest output
                warnings.warn(
                    f"{operation_name} exception for test {test_case.id}: {str(e)}",
                    UserWarning,
                    stacklevel=2,
                )

    elapsed_time = time.time() - start_time
    print(
        f"\n🕐 {operation_name} completed in {elapsed_time:.2f}s: {successful_test_cases} successful, {failed_test_cases} failed, {timed_out_test_cases} timeout"
    )


def run_test_setup(test_cases: List[HolmesTestCase]) -> None:
    """Run before_test for each test case in parallel."""
    run_test_commands(test_cases, before_test, "Setup")


def run_test_cleanup(test_cases: List[HolmesTestCase]) -> None:
    """Run after_test for each test case in parallel."""
    run_test_commands(test_cases, after_test, "Cleanup")


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
            ):
                test_cases.append(test_case)
                seen_ids.add(test_case.id)

    return test_cases
