# type: ignore
import logging
import os
import subprocess
from contextlib import contextmanager
from typing import Dict, Optional
from tests.llm.utils.test_case_utils import HolmesTestCase


def invoke_command(command: str, cwd: str) -> str:
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
        )

        output = f"{result.stdout}\n{result.stderr}"
        logging.debug(f"** `{command}`:\n{output}")
        logging.warning(f"Ran `{command}` in {cwd} with exit code {result.returncode}")
        return output
    except subprocess.CalledProcessError as e:
        message = f"Command `{command}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        logging.error(message)
        raise e


def before_test(test_case: HolmesTestCase):
    if test_case.before_test and os.environ.get("RUN_LIVE", "").strip().lower() in (
        "1",
        "true",
    ):
        commands = test_case.before_test.split("\n")
        for command in commands:
            invoke_command(command=command, cwd=test_case.folder)


def after_test(test_case: HolmesTestCase):
    if test_case.after_test and os.environ.get("RUN_LIVE", "").strip().lower() in (
        "1",
        "true",
    ):
        commands = test_case.after_test.split("\n")
        for command in commands:
            invoke_command(command=command, cwd=test_case.folder)


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
