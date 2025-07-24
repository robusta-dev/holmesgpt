# type: ignore
import logging
import os
import subprocess
import time
from contextlib import contextmanager
from typing import Dict, Optional
from tests.llm.utils.test_case_utils import HolmesTestCase


EVAL_SETUP_TIMEOUT = int(os.environ.get("EVAL_SETUP_TIMEOUT", "180"))


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

    @property
    def exit_info(self) -> str:
        """Get formatted exit information."""
        return (
            f"exit {self.exit_code}" if self.exit_code is not None else "no exit code"
        )


def _invoke_command(command: str, cwd: str) -> str:
    try:
        logging.debug(f"Running `{command}` in {cwd}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            timeout=EVAL_SETUP_TIMEOUT,
        )

        output = f"{result.stdout}\n{result.stderr}"
        logging.debug(f"** `{command}`:\n{output}")
        logging.warning(f"Ran `{command}` in {cwd} with exit code {result.returncode}")
        return output
    except subprocess.CalledProcessError as e:
        message = f"Command `{command}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        logging.error(message)
        raise e


def run_commands(
    test_case: HolmesTestCase, commands_str: str, operation: str
) -> CommandResult:
    """Generic command runner for setup/cleanup operations."""
    if not commands_str or os.environ.get("RUN_LIVE", "").strip().lower() not in (
        "1",
        "true",
    ):
        return CommandResult(
            command=f"(no {operation} needed)",
            test_case_id=test_case.id,
            success=True,
            elapsed_time=0,
        )

    start_time = time.time()
    commands = commands_str.strip().split("\n")
    combined_output = []

    try:
        for command in commands:
            if command.strip():  # Skip empty lines
                output = _invoke_command(command=command, cwd=test_case.folder)
                combined_output.append(f"$ {command}\n{output}")

        elapsed_time = time.time() - start_time
        return CommandResult(
            command=f"{operation.capitalize()}: {len(commands)} command(s)",
            test_case_id=test_case.id,
            success=True,
            elapsed_time=elapsed_time,
        )
    except subprocess.CalledProcessError as e:
        elapsed_time = time.time() - start_time
        error_details = "\n".join(combined_output)
        error_details += f"\n$ {e.cmd}\nExit code: {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"

        return CommandResult(
            command=f"{operation.capitalize()} failed at: {e.cmd}",
            test_case_id=test_case.id,
            success=False,
            exit_code=e.returncode,
            elapsed_time=elapsed_time,
            error_type="failure",
            error_details=error_details,
        )
    except subprocess.TimeoutExpired as e:
        elapsed_time = time.time() - start_time
        error_details = "\n".join(combined_output)
        error_details += f"\n$ {e.cmd}\nTIMEOUT after {e.timeout}s; You can increase timeout with environment variable EVAL_SETUP_TIMEOUT=<seconds>"

        return CommandResult(
            command=f"{operation.capitalize()} timeout: {e.cmd}",
            test_case_id=test_case.id,
            success=False,
            elapsed_time=elapsed_time,
            error_type="timeout",
            error_details=error_details,
        )
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_details = "\n".join(combined_output)
        error_details += f"\nUnexpected error: {str(e)}"

        return CommandResult(
            command=f"{operation.capitalize()} failed",
            test_case_id=test_case.id,
            success=False,
            elapsed_time=elapsed_time,
            error_type="failure",
            error_details=error_details,
        )


@contextmanager
def set_test_env_vars(test_case: HolmesTestCase):
    """Context manager to set and restore environment variables for test execution."""
    if not test_case.test_env_vars:
        yield
        return

    # Save current environment variable values
    saved_env_vars: Dict[str, Optional[str]] = {}
    for key in test_case.test_env_vars.keys():
        saved_env_vars[key] = os.environ.get(key)

    try:
        # Set test environment variables
        for key, value in test_case.test_env_vars.items():
            os.environ[key] = value

        yield
    finally:
        # Restore original environment variable values
        for key, original_value in saved_env_vars.items():
            if original_value is None:
                # Variable didn't exist before, remove it
                if key in os.environ:
                    del os.environ[key]
            else:
                # Variable existed before, restore original value
                os.environ[key] = original_value
