import os, logging, multiprocessing

from pipelines_declarative_executor.model.report import ReportUploadMode
from pipelines_declarative_executor.utils.string_utils import StringUtils


class EnvVar:
    MAX_CONCURRENT_STAGES = int(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_MAX_CONCURRENT_STAGES', max(1, multiprocessing.cpu_count())))
    GLOBAL_CONFIGS_PREFIX = os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_GLOBAL_CONFIGS_PREFIX', "CUSTOM_GLOBAL_CONFIG")
    ENABLE_FULL_EXECUTION_LOG = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_FULL_EXECUTION_LOG', True))
    ENABLE_PROFILER_STATS = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_PROFILER_STATS', False))
    ENABLE_MODULE_STDOUT_LOG = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_MODULE_STDOUT_LOG', True))
    ENABLE_DEBUG_DATA_COLLECTOR = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_DEBUG_DATA_COLLECTOR', True))
    AUTH_RULES_NAME = "PIPELINES_DECLARATIVE_EXECUTOR_AUTH_RULES"

    REPORT_REMOTE_ENDPOINTS_NAME = "PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS"
    REPORT_SEND_MODE = ReportUploadMode(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_MODE', ReportUploadMode.ON_COMPLETION))
    REPORT_SEND_INTERVAL = float(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_INTERVAL', 5))
    REPORT_STATUS_POLL_INTERVAL = float(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_REPORT_STATUS_POLL_INTERVAL', 0.5))

    ENCRYPT_OUTPUT_PARAMS = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_ENCRYPT_OUTPUT_SECURE_PARAMS', True))
    FAIL_ON_MISSING_SOPS = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_FAIL_ON_MISSING_SOPS', True))

    SHELL_PROCESS_TIMEOUT = int(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_SHELL_PROCESS_TIMEOUT', 30))
    SOPS_PROCESS_TIMEOUT = int(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_SOPS_PROCESS_TIMEOUT', 10))

    EXECUTION_URL = os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL', None)
    EXECUTION_USER = os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_USER', None)
    EXECUTION_EMAIL = os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_EMAIL', None)

    PYTHON_MODULE_PATH = os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH', None)

    # DEBUG ONLY
    IS_LOCAL_DEBUG = StringUtils.to_bool(os.getenv('PIPELINES_DECLARATIVE_EXECUTOR_IS_LOCAL_DEBUG', False))


class EnvVarUtils:
    @staticmethod
    def load_config_from_file_or_from_value(env_var_name: str) -> str | None:
        """Load configuration from either a file or environment variable. """
        file_path_var = f"{env_var_name}_FILE_PATH"

        if file_path := os.getenv(file_path_var):
            try:
                logging.debug(f"Loading configuration from file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return content
            except FileNotFoundError:
                logging.warning(f"Configuration file not found: {file_path}, falling back to environment variable")
            except Exception as e:
                logging.warning(f"Error reading configuration file {file_path}: {e}, falling back to environment variable")

        direct_value = os.getenv(env_var_name)
        if direct_value is not None:
            logging.debug(f"Loading configuration from environment variable: {env_var_name}")
            return direct_value

        logging.debug(f"No configuration found for {env_var_name}")
        return None

    @staticmethod
    def get_value_or_from_env(data: dict, property_name: str) -> str | None:
        value = data.get(f"{property_name}_value")
        if not value:
            value = os.getenv(data.get(f"{property_name}_env_var", ''))
        if value:
            return value
