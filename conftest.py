import os
import logging
from tests.llm.conftest import show_llm_summary_report
from holmes.core.tracing import readable_timestamp, get_active_branch_name
from tests.llm.utils.braintrust import get_braintrust_url


def pytest_addoption(parser):
    """Add custom pytest command line options"""
    parser.addoption(
        "--generate-mocks",
        action="store_true",
        default=False,
        help="Generate mock data files during test execution instead of using existing mocks",
    )
    parser.addoption(
        "--regenerate-all-mocks",
        action="store_true",
        default=False,
        help="Regenerate all mock data files, replacing existing ones (implies --generate-mocks)",
    )
    parser.addoption(
        "--skip-setup",
        action="store_true",
        default=False,
        help="Skip running before_test commands for test cases (useful for iterative test development)",
    )
    parser.addoption(
        "--skip-cleanup",
        action="store_true",
        default=False,
        help="Skip running after_test commands for test cases (useful for debugging test failures)",
    )


def pytest_configure(config):
    """Configure pytest settings"""
    # Configure worker-specific log files for xdist compatibility
    # worker_id = getattr(config, "workerinput", {}).get("workerid", "master")
    # if worker_id != "master":
    #    # Set worker-specific log file to avoid conflicts
    #    config.option.log_file = f"tests-{worker_id}.log"

    # Determine worker id
    # Also see: https://pytest-xdist.readthedocs.io/en/latest/how-to.html#creating-one-log-file-for-each-worker
    # worker_id = os.environ.get("PYTEST_XDIST_WORKER", default="gw0")

    # # Create logs folder
    # logs_folder = os.environ.get("LOGS_FOLDER", default="logs_folder")
    # os.makedirs(logs_folder, exist_ok=True)

    # # Create file handler to output logs into corresponding worker file
    # file_handler = logging.FileHandler(f"{logs_folder}/logs_worker_{worker_id}.log", mode="w")
    # file_handler.setFormatter(
    #     logging.Formatter(
    #         fmt="{asctime} {levelname}:{name}:{lineno}:{message}",
    #         style="{",
    #     )
    # )
    # # Create stream handler to output logs on console
    # # This is a workaround for a known limitation:
    # # https://pytest-xdist.readthedocs.io/en/latest/known-limitations.html
    # console_handler = logging.StreamHandler(sys.stderr)  # pytest only prints error logs
    # console_handler.setFormatter(
    #     logging.Formatter(
    #         # Include worker id in log messages, \r is needed to separate lines in console
    #         fmt="\r{asctime} " + worker_id + ":{levelname}:{name}:{lineno}:{message}",
    #         style="{",
    #     )
    # )
    # # Configure logging
    # logging.basicConfig(level=logging.INFO, force=True, handlers=[console_handler, file_handler])

    # Suppress noisy LiteLLM logs during testing
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    # Also suppress the verbose logger used by LiteLLM
    logging.getLogger("LiteLLM.verbose_logger").setLevel(logging.ERROR)
    # Suppress litellm sub-loggers
    logging.getLogger("litellm").setLevel(logging.ERROR)
    logging.getLogger("litellm.cost_calculator").setLevel(logging.ERROR)
    logging.getLogger("litellm.litellm_core_utils").setLevel(logging.ERROR)
    logging.getLogger("litellm.litellm_core_utils.litellm_logging").setLevel(
        logging.ERROR
    )
    # Suppress httpx HTTP request logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if not os.getenv("EXPERIMENT_ID"):
        try:
            username = os.getlogin()
        except OSError:
            # os.getlogin() fails in environments without a terminal (e.g., GitHub Actions)
            username = os.getenv("USER", "ci")
        git_branch = get_active_branch_name()
        os.environ["EXPERIMENT_ID"] = f"{username}-{git_branch}-{readable_timestamp()}"


def pytest_report_header(config):
    braintrust_api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not braintrust_api_key:
        return ""

    experiment_url = get_braintrust_url()
    clickable_url = f"\033]8;;{experiment_url}\033\\{experiment_url}\033]8;;\033\\"
    return f"Eval results: (link valid once setup completes): {clickable_url}"


# due to pytest quirks, we need to define this in the main conftest.py - when defined in the llm conftest.py it
# is SOMETIMES picked up and sometimes not, depending on how the test was invokedr
pytest_terminal_summary = show_llm_summary_report
