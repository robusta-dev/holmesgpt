
import logging
import subprocess
from tests.llm.utils.mock_utils import HolmesTestCase

def invoke_command(
        command: str,
        cwd:str
    ) -> str:
    try:
        logging.debug(f"Running `{command}` in {cwd}")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL, cwd=cwd
        )

        output = f"{result.stdout}\n{result.stderr}"
        logging.debug(f"** `{command}`:\n{output}")
        logging.info(f"Ran `{command}` in {cwd} with exit code {result.returncode}")
        return output
    except subprocess.CalledProcessError as e:
        message = f"Command `{command}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        logging.error(message)
        raise e

def before_test(test_case:HolmesTestCase):
    if test_case.before_test:
        invoke_command(command=test_case.before_test, cwd=test_case.folder)

def after_test(test_case:HolmesTestCase):
    if test_case.after_test:
        invoke_command(command=test_case.after_test, cwd=test_case.folder)
