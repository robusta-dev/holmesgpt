from typing import Tuple


def callable_success() -> Tuple[bool, str]:
    return True, ""


def callable_failure_with_message() -> Tuple[bool, str]:
    return False, "Callable check failed"


def callable_failure_no_message() -> Tuple[bool, str]:
    return False, ""


def failing_callable_for_test():
    raise Exception("Failure in callable prerequisite")
