from __future__ import annotations

import sys, logging

from logging import Logger
from pathlib import Path

from pipelines_declarative_executor.utils.env_var_utils import EnvVar


class LoggingUtils:
    FILE_LOG_LEVEL = logging.DEBUG
    CONSOLE_LOG_LEVEL = logging.INFO
    EXECUTION_LOG_NAME = "execution.log"
    FULL_EXECUTION_LOG_NAME = "full_execution.log"
    DEFAULT_FORMAT = u'[%(asctime)s] [%(levelname)-5s] [class=%(filename)s:%(lineno)-3s] %(message)s'

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
        logged_vars = {
            "GENERAL": [
                "GLOBAL_CONFIGS_PREFIX", "PYTHON_MODULE_PATH"
            ],
            "DEBUG": [
                "IS_LOCAL_DEBUG", "ENABLE_FULL_EXECUTION_LOG",
                "ENABLE_MODULE_STDOUT_LOG", "ENABLE_DEBUG_DATA_COLLECTOR"
            ],
            "REMOTE REPORT": [
                "REPORT_SEND_MODE", "REPORT_SEND_INTERVAL", "REPORT_STATUS_POLL_INTERVAL"
            ],
            "ENCRYPTION": [
                "ENCRYPT_OUTPUT_PARAMS", "FAIL_ON_MISSING_SOPS"
            ],
            "SUBPROCESSES": [
                "SHELL_PROCESS_TIMEOUT", "SOPS_PROCESS_TIMEOUT"
            ],
            "RESOURCE MANAGEMENT": [
                "ENABLE_RESOURCE_MANAGER", "MAX_CONCURRENT_STAGES",
                "REQUIRED_MEMORY_PER_SUBPROCESS", "RESOURCE_MANAGER_QUEUE_TIMEOUT"
            ],
            "PROFILING": [
                "ENABLE_PROFILER_STATS",
                "ENABLE_STAGE_RESOURCE_USAGE_PROFILING", "STAGE_RESOURCE_USAGE_PROFILING_INTERVAL",
                "ENABLE_PEAK_RESOURCE_USAGE_PROFILING", "PEAK_RESOURCE_USAGE_PROFILING_INTERVAL"
            ],
            "WRAPPER VARS": [
                "EXECUTION_URL", "EXECUTION_USER", "EXECUTION_EMAIL"
            ],
        }
        env_info = ""
        for section, var_names in logged_vars.items():
            env_info += f"\n> {section}:\n"
            env_info += "\n".join([f"    {var_name}: {getattr(EnvVar, var_name)}" for var_name in var_names])
        logging.info(env_info)
