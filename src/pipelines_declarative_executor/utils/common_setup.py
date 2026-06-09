import sys, logging

from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils
from pipelines_declarative_executor.utils.python_module_utils import PythonModuleUtils


class CommonSetup:
    @staticmethod
    def setup_cli(log_level: str = "INFO", log_env_vars: bool = True):
        CommonSetup.setup_cli_logging(log_level, log_env_vars)
        PythonModuleUtils.prepare_python_module()
        CommonSetup.set_recursion_limit()

    @staticmethod
    def setup_cli_logging(log_level: str = "INFO", log_env_vars: bool = True):
        LoggingUtils.CONSOLE_LOG_LEVEL = getattr(logging, log_level.upper(), logging.INFO)
        LoggingUtils.configure_root_logger()
        if log_env_vars:
            LoggingUtils.log_env_vars()

    @staticmethod
    def set_recursion_limit():
        if sys.getrecursionlimit() != EnvVar.RECURSION_LIMIT:
            sys.setrecursionlimit(EnvVar.RECURSION_LIMIT)
            logging.info(f"Recursion limit set to {EnvVar.RECURSION_LIMIT}")
