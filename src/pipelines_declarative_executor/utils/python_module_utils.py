import os, logging


class PythonModuleUtils:
    @staticmethod
    def prepare_python_module():
        from pipelines_declarative_executor.utils.env_var_utils import EnvVar
        module_path = EnvVar.PYTHON_MODULE_PATH
        if not EnvVar.PREPARE_PYTHON_MODULE or not module_path or not (module_path.endswith(".pyz") or module_path.endswith(".zip")):
            return
        base, ext = os.path.splitext(module_path)
        EnvVar.PYTHON_MODULE_PATH = base
        if os.path.exists(base):
            logging.info("Python Module already prepared")
            return
        os.makedirs(base, exist_ok=True)
        from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
        ArchiveUtils.unarchive(module_path, base)
        logging.info(f"Prepared Python Module (extracted into {base})")
