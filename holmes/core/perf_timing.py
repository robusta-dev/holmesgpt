import time
import logging
from contextlib import contextmanager

from functools import wraps

class PerfTiming:
    def __init__(self, name):
        self.ended = False

        self.name = name
        self.start_time = time.time()
        self.last_measure_time = self.start_time
        self.last_measure_label = "Start"
        self.timings = []

    def measure(self, label):
        if self.ended:
            raise Exception("cannot measure a perf timing that is already ended")
        current_time = time.time()

        time_since_start = int((current_time - self.start_time) * 1000)
        time_since_last = int((current_time - self.last_measure_time) * 1000)

        self.timings.append((label, time_since_last, time_since_start))

        self.last_measure_time = current_time
        self.last_measure_label = label

    def end(self):
        self.ended = True
        current_time = time.time()
        time_since_start = int((current_time - self.start_time) * 1000)
        message = f'{self.name}(TOTAL) {time_since_start}ms'
        logging.info(message)
        for label, time_since_last, time_since_start in self.timings:
            logging.info(f'    {self.name}({label}) +{time_since_last}ms  {time_since_start}ms')

def log_function_timing(func):
    @wraps(func)
    def function_timing_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = int((end_time - start_time) * 1000)
        logging.info(f'Function "{func.__name__}()" took {total_time}ms')
        return result
    return function_timing_wrapper
