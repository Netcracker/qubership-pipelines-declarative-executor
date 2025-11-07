import logging, subprocess, unittest, functools


class ExecutorTestCase(unittest.TestCase):

    def __init__(self, methodName = "runTest"):
        super().__init__(methodName)
        self.exec_dir = None

    @staticmethod
    def with_exec_dir(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            self.exec_dir = f"/{func.__name__}"
            return func(self, *args, **kwargs)

        return wrapper

    def _run_and_log(self, command):
        logging.info(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        if result.stdout:
            logging.info(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            logging.info(f"STDERR:\n{result.stderr}")
        logging.info(f"Return code: {result.returncode}")
        return result
