# type: ignore
from typing import Optional, List, Dict, Any
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
import yaml
import tempfile

from rich.console import Console
from holmes.core.tracing import TracingFactory
from holmes.config import Config
from holmes.checks import (
    CheckRunner,
    CheckMode,
    load_checks_config,
    CheckStatus,
)
from tests.llm.utils.commands import set_test_env_vars
from tests.llm.utils.mock_toolset import (
    MockToolsetManager,
    MockMode,
    MockGenerationConfig,
)
from tests.llm.utils.test_case_utils import (
    HolmesTestCase,
    check_and_skip_test,
)
from tests.llm.utils.property_manager import (
    set_initial_properties,
    update_test_results,
    update_mock_error,
)
from os import path
from holmes.core.tracing import SpanType
from tests.llm.utils.iteration_utils import get_test_cases

TEST_CASES_FOLDER = Path(
    path.abspath(path.join(path.dirname(__file__), "fixtures", "test_holmes_check"))
)


class CheckTestCase(HolmesTestCase):
    """Test case for holmes check command."""

    checks: List[Dict[str, Any]]  # Check configurations
    destinations: Optional[Dict[str, Any]] = None  # Destination configurations
    defaults: Optional[Dict[str, Any]] = None  # Default check settings
    expected_results: Dict[str, str]  # Expected pass/fail for each check by name


def get_holmes_check_test_cases():
    """Load all test cases from the test_holmes_check fixtures folder."""
    return get_test_cases(TEST_CASES_FOLDER)


def evaluate_check_correctness(
    expected_results: Dict[str, str],
    actual_results: Dict[str, CheckStatus],
) -> float:
    """
    Evaluate if check results match expected pass/fail status.

    Returns:
        1.0 if all checks match expected status, 0.0 otherwise
    """
    if not expected_results or not actual_results:
        return 0.0

    for check_name, expected_status in expected_results.items():
        actual_status = actual_results.get(check_name)

        if not actual_status:
            print(f"   ❌ Check '{check_name}' not found in results")
            return 0.0

        # Convert expected string to CheckStatus
        expected_status_enum = (
            CheckStatus.PASS if expected_status.lower() == "pass" else CheckStatus.FAIL
        )

        if actual_status != expected_status_enum:
            print(
                f"   ❌ Check '{check_name}': expected {expected_status}, got {actual_status.value}"
            )
            return 0.0

        print(f"   ✅ Check '{check_name}': {actual_status.value} (matches expected)")

    return 1.0


def run_holmes_check(
    test_case: CheckTestCase,
    tracer,
    eval_span,
    mock_generation_config: MockGenerationConfig,
    request,
) -> Dict[str, CheckStatus]:
    """Run holmes check with the test case configuration."""

    # Create temporary checks file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        checks_config = {
            "version": 1,
            "checks": test_case.checks,
        }

        if test_case.destinations:
            checks_config["destinations"] = test_case.destinations

        if test_case.defaults:
            checks_config["defaults"] = test_case.defaults

        yaml.dump(checks_config, f)
        checks_file = Path(f.name)

    try:
        # Load config
        config = Config.load_from_env()
        console = Console()

        # Create mock toolset manager if in mock mode
        if mock_generation_config.mode == MockMode.MOCK:
            test_case_folder = Path(test_case.folder)
            manager = MockToolsetManager(
                test_case_folder,
                mock_generation_config.generate_mocks,
                config,
                console,
                mock_generation_config.mode,
            )
            tool_executor = manager.load()
        else:
            tool_executor = config.create_console_tool_executor(
                dal=None, refresh_status=False
            )

        # Create check runner
        runner = CheckRunner(
            config=config,
            console=console,
            mode=CheckMode.MONITOR,  # Always use monitor mode for tests
            verbose=True,
        )

        if mock_generation_config.mode == MockMode.MOCK:
            # In mock mode, we still use the mock toolset manager but let the LLM run
            runner.ai = config.create_console_toolcalling_llm(
                dal=None, refresh_toolsets=False, tracer=tracer
            )
            runner.ai.tool_executor = tool_executor
        else:
            # In live mode, use real tools and real LLM
            runner.ai = config.create_console_toolcalling_llm(
                dal=None, refresh_toolsets=False, tracer=tracer
            )

        # Load checks configuration
        checks_config = load_checks_config(checks_file)

        # Run checks
        results = runner.run_checks(
            checks=checks_config.checks,
            destinations_config=checks_config.destinations,
        )

        # Convert results to dict of status by check name
        results_dict = {result.check_name: result.status for result in results}

        return results_dict

    finally:
        # Clean up temp file
        if checks_file.exists():
            checks_file.unlink()


@pytest.mark.llm
@pytest.mark.parametrize("test_case", get_holmes_check_test_cases())
def test_holmes_check(
    test_case: CheckTestCase,
    caplog,
    request,
    mock_generation_config: MockGenerationConfig,
    shared_test_infrastructure,  # type: ignore
):
    """Test holmes check command with various check configurations."""

    # Set initial properties
    set_initial_properties(request, test_case)

    # Check if test should be skipped
    check_and_skip_test(test_case)

    # Check for setup failures
    setup_failures = shared_test_infrastructure.get("setup_failures", {})
    if test_case.id in setup_failures:
        request.node.user_properties.append(("is_setup_failure", True))
        pytest.fail(f"Test setup failed: {setup_failures[test_case.id]}")

    print(f"\n🧪 TEST: {test_case.id}")
    print("   CONFIGURATION:")
    print(
        f"   • Mode: {'⚪️ MOCKED' if mock_generation_config.mode == MockMode.MOCK else '🔥 LIVE'}"
    )
    print(f"   • Checks: {len(test_case.checks)} checks")
    print(f"   • Expected Results: {test_case.expected_results}")

    if test_case.before_test:
        print(f"   • Before Test: {test_case.before_test}")
    if test_case.after_test:
        print(f"   • After Test: {test_case.after_test}")

    tracer = TracingFactory.create_tracer("braintrust")
    tracer.start_experiment()

    actual_results: Optional[Dict[str, CheckStatus]] = None

    try:
        with tracer.start_trace(
            name=test_case.id, span_type=SpanType.EVAL
        ) as eval_span:
            # Store span info
            if hasattr(eval_span, "id"):
                request.node.user_properties.append(
                    ("braintrust_span_id", str(eval_span.id))
                )
            if hasattr(eval_span, "root_span_id"):
                request.node.user_properties.append(
                    ("braintrust_root_span_id", str(eval_span.root_span_id))
                )

            # Mock datetime if needed
            if test_case.mocked_date:
                mocked_datetime = datetime.fromisoformat(
                    test_case.mocked_date.replace("Z", "+00:00")
                )
                with patch("holmes.plugins.prompts.datetime") as mock_datetime:
                    mock_datetime.now.return_value = mocked_datetime
                    with set_test_env_vars(test_case):
                        actual_results = run_holmes_check(
                            test_case=test_case,
                            tracer=tracer,
                            eval_span=eval_span,
                            mock_generation_config=mock_generation_config,
                            request=request,
                        )
            else:
                with set_test_env_vars(test_case):
                    actual_results = run_holmes_check(
                        test_case=test_case,
                        tracer=tracer,
                        eval_span=eval_span,
                        mock_generation_config=mock_generation_config,
                        request=request,
                    )

    except Exception as e:
        # Log error to span
        try:
            if "eval_span" in locals():
                eval_span.log(
                    input=str(test_case.checks),
                    output=str(actual_results) if actual_results else str(e),
                    expected=str(test_case.expected_results),
                    dataset_record_id=test_case.id,
                    scores={},
                    tags=test_case.tags or [],
                )
        except Exception:
            pass

        # Check if this is a MockDataError
        is_mock_error = "MockDataError" in type(e).__name__ or any(
            "MockData" in base.__name__ for base in type(e).__mro__
        )

        if is_mock_error:
            update_mock_error(request, e)

        raise

    # Evaluate correctness
    score = evaluate_check_correctness(
        test_case.expected_results,
        actual_results or {},
    )

    print("\n   📊 EVALUATION:")
    print(f"   • Score: {score}")

    # Log to span
    eval_span.log(
        input=str(test_case.checks),
        output=str(actual_results),
        expected=str(test_case.expected_results),
        dataset_record_id=test_case.id,
        scores={"correctness": score},
        tags=test_case.tags or [],
    )

    # Update test results
    update_test_results(
        request,
        test_case,
        {"correctness": score},
        actual_output=str(actual_results),
        num_tool_calls=0,  # Not tracking tool calls for check tests
    )

    # Assert the test passes
    assert (
        score == 1.0
    ), f"Check results did not match expected: {actual_results} vs {test_case.expected_results}"
