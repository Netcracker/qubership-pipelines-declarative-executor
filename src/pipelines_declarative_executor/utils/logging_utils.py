from __future__ import annotations

import io, sys, logging, time

from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from pstats import SortKey

from pipelines_declarative_executor.utils.env_var_utils import EnvVar


class LoggingUtils:
    FILE_LOG_LEVEL = logging.DEBUG
    CONSOLE_LOG_LEVEL = logging.INFO
    EXECUTION_LOG_NAME = "execution.log"
    FULL_EXECUTION_LOG_NAME = "full_execution.log"
    DEFAULT_FORMAT = u'[%(asctime)s] [%(levelname)-5s] [class=%(filename)s:%(lineno)-3s] %(message)s'

    class Timer:
        def __enter__(self):
            self.start_time = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.elapsed_time_ms = (time.perf_counter() - self.start_time) * 1_000

    @staticmethod
    @contextmanager
    def time_it(message: str = ''):
        message = f"{message} - " if message else ''
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            elapsed = end - start
            logging.info(f"{message}Executed in {elapsed:.6f} seconds")

    @staticmethod
    @contextmanager
    def profile_it():
        if not EnvVar.ENABLE_PROFILER_STATS:
            yield
            return
        import cProfile, pstats
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            yield
        finally:
            profiler.disable()
            stats_stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream)
            stats.sort_stats(SortKey.TIME)
            stats.print_stats(30)
            logging.info("PROFILING RESULT:\n%s", stats_stream.getvalue())

    @staticmethod
    def configure_root_logger() -> Logger:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(LoggingUtils.CONSOLE_LOG_LEVEL)
        console_handler.setFormatter(logging.Formatter(LoggingUtils.DEFAULT_FORMAT))
        root_logger.addHandler(console_handler)

        if EnvVar.ENABLE_FULL_EXECUTION_LOG:
            file_handler = logging.FileHandler(LoggingUtils.FULL_EXECUTION_LOG_NAME, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(LoggingUtils.DEFAULT_FORMAT))
            root_logger.addHandler(file_handler)

        return root_logger

    @staticmethod
    def configure_logger(exec_dir: Path) -> Logger:
        logger = logging.getLogger(f"pipelines_declarative_executor_{exec_dir.as_posix()}")
        logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(exec_dir.joinpath(LoggingUtils.EXECUTION_LOG_NAME), encoding="utf-8")
        file_handler.setLevel(LoggingUtils.FILE_LOG_LEVEL)
        file_handler.setFormatter(logging.Formatter(LoggingUtils.DEFAULT_FORMAT))
        logger.addHandler(file_handler)

        return logger

    @staticmethod
    def get_log_level_name():
        return logging.getLevelName(LoggingUtils.CONSOLE_LOG_LEVEL)

    @staticmethod
    def log_env_vars():
        logged_vars = [
            "MAX_CONCURRENT_STAGES", "GLOBAL_CONFIGS_PREFIX",
            "ENABLE_FULL_EXECUTION_LOG", "ENABLE_PROFILER_STATS", "ENABLE_MODULE_STDOUT_LOG",
            "REPORT_SEND_MODE", "REPORT_SEND_INTERVAL", "REPORT_STATUS_POLL_INTERVAL",
            "ENCRYPT_OUTPUT_PARAMS", "FAIL_ON_MISSING_SOPS",
            "SHELL_PROCESS_TIMEOUT", "SOPS_PROCESS_TIMEOUT",
            "PYTHON_MODULE_PATH", "EXECUTION_URL", "EXECUTION_USER", "EXECUTION_EMAIL",
            "IS_LOCAL_DEBUG",
        ]
        env_info = "\n".join([f"{var_name}: {getattr(EnvVar, var_name)}" for var_name in logged_vars])
        logging.info(env_info)
