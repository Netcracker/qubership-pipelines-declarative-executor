import os, yaml, subprocess, shutil, tempfile

from functools import wraps
from pipelines_declarative_executor.model.exceptions import SopsException
from pipelines_declarative_executor.utils.env_var_utils import EnvVar


def requires_sops_init(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        SOPS.init()
        return func(*args, **kwargs)
    return wrapper


class SopsUtils:
    @staticmethod
    def load_and_decrypt_yaml(yaml_string: str) -> tuple[dict, bool]:
        yaml_dict = yaml.safe_load(yaml_string)
        is_encrypted = SOPS.is_encrypted(yaml_dict)
        if is_encrypted:
            yaml_dict = yaml.safe_load(SOPS.decrypt(yaml_string))
        return yaml_dict, is_encrypted


class SOPS:
    _is_init: bool = False
    _binary_path: str = 'sops'

    @staticmethod
    def init():
        if SOPS._is_init:
            return
        sops_path = shutil.which(SOPS._binary_path)
        if not sops_path:
            raise SopsException("SOPS binary not found in PATH!")
        if missing_vars := [var for var in ['SOPS_AGE_RECIPIENTS', 'SOPS_AGE_KEY'] if not os.getenv(var)]:
            raise SopsException(
                f"Missing required SOPS environment variables: {', '.join(missing_vars)}. "
                "Please set SOPS_AGE_RECIPIENTS (public key for encryption) and SOPS_AGE_KEY (private key for decryption) environment variables."
            )
        SOPS._is_init = True

    @staticmethod
    @requires_sops_init
    def encrypt(yaml_value: str) -> str:
        try:
            return SOPS._execute_sops_command(
                ['--encrypt'],
                yaml_value
            ).strip()
        except Exception as e:
            raise SopsException(e)

    @staticmethod
    @requires_sops_init
    def decrypt(yaml_value: str) -> str:
        try:
            return SOPS._execute_sops_command(
                ['--decrypt'],
                yaml_value
            ).strip()
        except Exception as e:
            raise SopsException(e)

    @staticmethod
    def is_encrypted(yaml_dict: dict) -> bool:
        return yaml_dict.get('sops', {}).get('age') is not None

    @staticmethod
    def _execute_sops_command(args: list, input_data: str) -> str:
        input_temp_file = None
        output_temp_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(input_data)
                input_temp_file = f.name
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                output_temp_file = f.name

            cmd = [SOPS._binary_path] + args + ['--output', output_temp_file, input_temp_file]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=EnvVar.SHELL_PROCESS_TIMEOUT
            )
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                raise Exception(f"SOPS command failed (return code {result.returncode}): {error_msg}")

            with open(output_temp_file, 'r') as f:
                output = f.read()
            return output

        except subprocess.TimeoutExpired:
            raise Exception("SOPS command timed out")
        finally:
            try:
                pass
                if input_temp_file and os.path.exists(input_temp_file):
                    os.unlink(input_temp_file)
                if output_temp_file and os.path.exists(output_temp_file):
                    os.unlink(output_temp_file)
            except Exception:
                pass
