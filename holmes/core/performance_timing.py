import time
import logging

from functools import wraps

from holmes.common.env_vars import (
    LOG_PERFORMANCE,
)


class PerformanceTiming:
    def __init__(self, name):
        self.ended = False

        self.name = name
        self.start_time = time.time()
        self.last_measure_time = self.start_time
        self.last_measure_label = "Start"
        self.timings = []

    def measure(self, label):
        if not LOG_PERFORMANCE:
            return
        if self.ended:
            raise Exception("cannot measure a perf timing that is already ended")
        current_time = time.time()

        time_since_start = int((current_time - self.start_time) * 1000)
        time_since_last = int((current_time - self.last_measure_time) * 1000)

        self.timings.append((label, time_since_last, time_since_start))

        self.last_measure_time = current_time
        self.last_measure_label = label

    def end(self, custom_message: str = ""):
        if not LOG_PERFORMANCE:
            return
        self.ended = True
        current_time = time.time()
        time_since_start = int((current_time - self.start_time) * 1000)
        message = f"{self.name} {custom_message} {time_since_start}ms"
        logging.info(message)
        if LOG_PERFORMANCE:
            for label, time_since_last, time_since_start in self.timings:
                logging.info(
                    f"\t{self.name}({label}) +{time_since_last}ms  {time_since_start}ms"
                )


def log_function_timing(label=None):
    def decorator(func):
        @wraps(func)
        def function_timing_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            total_time = int((end_time - start_time) * 1000)

            function_identifier = (
                f'"{label}: {func.__name__}()"' if label else f'"{func.__name__}()"'
            )
            logging.info(f"Function {function_identifier} took {total_time}ms")
            return result

        return function_timing_wrapper

    if callable(label):
        func = label
        label = None
        return decorator(func)
    return decorator
