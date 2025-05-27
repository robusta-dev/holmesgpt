import logging
import os
import subprocess
from tests.llm.utils.mock_utils import HolmesTestCase


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
        logging.info(f"Ran `{command}` in {cwd} with exit code {result.returncode}")
        return output
    except subprocess.CalledProcessError as e:
        message = f"Command `{command}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        logging.error(message)
        raise e


def before_test(test_case: HolmesTestCase):
    if test_case.before_test and os.environ.get("RUN_LIVE", "").strip().lower() in ("1", "true"):
        commands = test_case.before_test.split("\n")
        for command in commands:
            invoke_command(command=command, cwd=test_case.folder)


def after_test(test_case: HolmesTestCase):
    if test_case.after_test and os.environ.get("RUN_LIVE", "").strip().lower() in ("1", "true"):
        commands = test_case.after_test.split("\n")
        for command in commands:
            invoke_command(command=command, cwd=test_case.folder)
