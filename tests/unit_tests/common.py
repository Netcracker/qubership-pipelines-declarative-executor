import logging, subprocess, unittest


class ExecutorTestCase(unittest.TestCase):
    def _run_and_log(self, command):
        logging.info(f"Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        if result.stdout:
            logging.info(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            logging.info(f"STDERR:\n{result.stderr}")
        logging.info(f"Return code: {result.returncode}")
        return result
