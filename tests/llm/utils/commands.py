# type: ignore
import logging
import os
import subprocess
from tests.llm.utils.mock_utils import HolmesTestCase


def invoke_command(
    command: str, cwd: str, test_case_id: str = None, timeout: int = 70
) -> str:
    import time

    try:
        test_prefix = f"[{test_case_id}]" if test_case_id else ""
        print(f"⏳ {test_prefix} Starting: {command} (in {cwd})")
        logging.debug(f"{test_prefix} Running `{command}` in {cwd}")

        start_time = time.time()
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

        output = f"{result.stdout}\n{result.stderr}"
        logging.debug(f"{test_prefix} `{command}`:\n{output}")
        print(
            f"✅ {test_prefix} Ran: {command} (exit code: {result.returncode}, {elapsed_time:.2f}s)"
        )
        return output
    except subprocess.TimeoutExpired as e:
        elapsed_time = time.time() - start_time
        test_prefix = f"[{test_case_id}]" if test_case_id else ""
        message = f"{test_prefix} Command `{command}` timed out after {timeout} seconds"
        logging.error(message)
        print(f"⏰ {test_prefix} TIMEOUT: {command} (after {elapsed_time:.2f}s)")
        raise e
    except subprocess.CalledProcessError as e:
        elapsed_time = time.time() - start_time
        test_prefix = f"[{test_case_id}]" if test_case_id else ""
        message = f"{test_prefix} Command `{command}` failed with return code {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        logging.error(message)
        print(
            f"❌ {test_prefix} Failed: {command} (exit code: {e.returncode}, {elapsed_time:.2f}s)"
        )
        raise e


def before_test(test_case: HolmesTestCase):
    if test_case.before_test and os.environ.get("RUN_LIVE", "").strip().lower() in (
        "1",
        "true",
    ):
        print(
            f"🚀 [{test_case.id}] BEFORE TEST - Setting up test environment for {test_case.id}:"
        )
        commands = test_case.before_test.split("\n")
        timeout = getattr(
            test_case, "timeout", 60
        )  # Default 60s, override with timeout field

        for command in commands:
            if command.strip():  # Skip empty commands
                try:
                    invoke_command(
                        command=command,
                        cwd=test_case.folder,
                        test_case_id=test_case.id,
                        timeout=timeout,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    print(
                        f"⚠️ [{test_case.id}] BEFORE TEST - Warning: Setup command failed but continuing: {command}"
                    )
                    logging.warning(
                        f"[{test_case.id}] Setup command failed: {command} - {str(e)}"
                    )
        print(f"✅ [{test_case.id}] BEFORE TEST - Setup completed for {test_case.id}")


def after_test(test_case: HolmesTestCase):
    if test_case.after_test and os.environ.get("RUN_LIVE", "").strip().lower() in (
        "1",
        "true",
    ):
        print(
            f"🧹 [{test_case.id}] AFTER TEST - Cleaning up test environment for {test_case.id}:"
        )
        commands = test_case.after_test.split("\n")
        timeout = getattr(
            test_case, "timeout", 60
        )  # Default 60s, override with timeout field

        for command in commands:
            if command.strip():  # Skip empty commands
                try:
                    invoke_command(
                        command=command,
                        cwd=test_case.folder,
                        test_case_id=test_case.id,
                        timeout=timeout,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    print(
                        f"⚠️ [{test_case.id}] AFTER TEST - Warning: Cleanup command failed but continuing: {command}"
                    )
                    logging.warning(
                        f"[{test_case.id}] Cleanup command failed: {command} - {str(e)}"
                    )
        print(f"✅ [{test_case.id}] AFTER TEST - Cleanup completed for {test_case.id}")
