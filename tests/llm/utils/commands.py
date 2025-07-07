# type: ignore
import os
import subprocess
from tests.llm.utils.mock_utils import HolmesTestCase


class CommandResult:
    def __init__(
        self,
        command: str,
        test_case_id: str,
        success: bool,
        exit_code: int = None,
        elapsed_time: float = 0,
        error_type: str = None,
        error_details: str = None,
    ):
        self.command = command
        self.test_case_id = test_case_id
        self.success = success
        self.exit_code = exit_code
        self.elapsed_time = elapsed_time
        self.error_type = error_type  # 'timeout', 'failure', or None
        self.error_details = error_details


def invoke_command(
    command: str, cwd: str, test_case_id: str = None, timeout: int = 70
) -> CommandResult:
    import time

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            timeout=timeout,
        )
        elapsed_time = time.time() - start_time
        return CommandResult(
            command=command,
            test_case_id=test_case_id,
            success=True,
            exit_code=result.returncode,
            elapsed_time=elapsed_time,
        )
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        return CommandResult(
            command=command,
            test_case_id=test_case_id,
            success=False,
            elapsed_time=elapsed_time,
            error_type="timeout",
            error_details=f"Command timed out after {timeout} seconds",
        )
    except subprocess.CalledProcessError as e:
        elapsed_time = time.time() - start_time
        return CommandResult(
            command=command,
            test_case_id=test_case_id,
            success=False,
            exit_code=e.returncode,
            elapsed_time=elapsed_time,
            error_type="failure",
            error_details=f"Exit code {e.returncode}\nstdout: {e.stdout}\nstderr: {e.stderr}",
        )


def before_test(test_case: HolmesTestCase):
    """Execute before_test commands and return single result for test case"""
    if not test_case.before_test or os.environ.get(
        "RUN_LIVE", ""
    ).strip().lower() not in ("1", "true"):
        return CommandResult(
            command="(no setup needed)",
            test_case_id=test_case.id,
            success=True,
            elapsed_time=0,
        )

    commands = test_case.before_test.split("\n")
    timeout = getattr(
        test_case, "timeout", 70
    )  # Default 70s, override with timeout field
    total_time = 0

    for command in commands:
        if command.strip():  # Skip empty commands
            result = invoke_command(
                command=command,
                cwd=test_case.folder,
                test_case_id=test_case.id,
                timeout=timeout,
            )
            total_time += result.elapsed_time

            # If any command fails, return failure for the whole test case
            if not result.success:
                # Format error details with proper indentation
                indented_details = "\n".join(
                    f"   {line}" for line in result.error_details.split("\n")
                )
                return CommandResult(
                    command=f"setup commands (failed at: {command})",
                    test_case_id=test_case.id,
                    success=False,
                    elapsed_time=total_time,
                    error_type=result.error_type,
                    error_details=f"Failed command: {command}\n{indented_details}",
                )

    # All commands succeeded
    return CommandResult(
        command="setup commands",
        test_case_id=test_case.id,
        success=True,
        elapsed_time=total_time,
    )


def after_test(test_case: HolmesTestCase):
    """Execute after_test commands and return single result for test case"""
    if not test_case.after_test or os.environ.get(
        "RUN_LIVE", ""
    ).strip().lower() not in ("1", "true"):
        return CommandResult(
            command="(no cleanup needed)",
            test_case_id=test_case.id,
            success=True,
            elapsed_time=0,
        )

    commands = test_case.after_test.split("\n")
    timeout = getattr(
        test_case, "timeout", 70
    )  # Default 70s, override with timeout field
    total_time = 0

    for command in commands:
        if command.strip():  # Skip empty commands
            result = invoke_command(
                command=command,
                cwd=test_case.folder,
                test_case_id=test_case.id,
                timeout=timeout,
            )
            total_time += result.elapsed_time

            # If any command fails, return failure for the whole test case
            if not result.success:
                # Format error details with proper indentation
                indented_details = "\n".join(
                    f"   {line}" for line in result.error_details.split("\n")
                )
                return CommandResult(
                    command=f"cleanup commands (failed at: {command})",
                    test_case_id=test_case.id,
                    success=False,
                    elapsed_time=total_time,
                    error_type=result.error_type,
                    error_details=f"Failed command: {command}\n{indented_details}",
                )

    # All commands succeeded
    return CommandResult(
        command="cleanup commands",
        test_case_id=test_case.id,
        success=True,
        elapsed_time=total_time,
    )
