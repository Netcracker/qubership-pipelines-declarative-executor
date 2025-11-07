# ruff: noqa: F821
from __future__ import annotations

import json, yaml, copy, shutil

from pathlib import Path
from pipelines_declarative_executor.model.stage import ExecutionStatus, Stage
from pipelines_declarative_executor.utils.constants import StatusCodes
from pipelines_declarative_executor.x_modules_ops.dict_utils import UtilsDictionary


class CommonUtils:
    @staticmethod
    def write_file(content: str, file: str | Path):
        with open(file, 'w') as fs:
            fs.write(content)

    @staticmethod
    def write_json(obj, file: str | Path, pretty: bool = False):
        with open(file, 'w') as fs:
            from pipelines_declarative_executor.utils.string_utils import StringUtils
            fs.write(json.dumps(obj, indent=(2 if pretty else None), default=StringUtils.json_encode))

    @staticmethod
    def dump_json(obj, pretty: bool = False) -> str:
        from pipelines_declarative_executor.utils.string_utils import StringUtils
        return json.dumps(obj, indent=(2 if pretty else None), default=StringUtils.json_encode)

    @staticmethod
    def load_json_file(file_path: str | Path) -> list | dict:
        with open(file_path) as file:
            return json.load(file)

    @staticmethod
    def load_yaml_file(file_path: str | Path) -> list | dict:
        with open(file_path) as file:
            return yaml.safe_load(file)

    @staticmethod
    def traverse(obj: dict | list, path: list = [], traverse_nested_lists: bool = True):
        for k, v in obj.items() if isinstance(obj, dict) else enumerate(obj):
            if isinstance(v, dict) or (traverse_nested_lists and isinstance(v, list)):
                for kv in CommonUtils.traverse(v, path + [k], traverse_nested_lists):
                    yield kv
            else:
                yield path + [k], v

    @staticmethod
    def recursive_merge(source_dict: dict, target_dict: dict) -> dict:
        """Recursively adds all keys from target_dict to a copy of source_dict"""
        source = copy.deepcopy(source_dict)
        target = copy.deepcopy(target_dict)
        if target is None:
            return source
        for key, value in target.items():
            if key in source and isinstance(source[key], dict) and isinstance(value, dict):
                source[key] = CommonUtils.recursive_merge(source[key], value)
            else:
                source[key] = value
        return source

    @staticmethod
    def create_exec_dir(execution_folder_path: str | Path, exists_ok: bool = False) -> Path:
        exec_dir = Path(execution_folder_path)
        if exec_dir.exists() and not exists_ok:
            if exec_dir.is_dir():
                shutil.rmtree(exec_dir)
            else:
                raise FileExistsError(f"Path '{execution_folder_path}' exists and is a file, not a directory.")
        exec_dir.mkdir(parents=True, exist_ok=exists_ok)
        return exec_dir

    @staticmethod
    def calculate_dict_values(execution: 'PipelineExecution', input_dict: dict) -> dict:
        calculated_dict = {}
        if input_dict:
            for path, value in CommonUtils.traverse(input_dict):
                value_calculated = execution.vars.calculate_expression(value)
                UtilsDictionary.setitem_by_path(calculated_dict, path, value_calculated)
        return calculated_dict

    @staticmethod
    def calculate_final_status(stages: list[Stage]) -> ExecutionStatus:
        if any(stage.status == ExecutionStatus.CANCELLED for stage in stages):
            return ExecutionStatus.CANCELLED
        if any(stage.status == ExecutionStatus.FAILED for stage in stages):
            return ExecutionStatus.FAILED
        return ExecutionStatus.SUCCESS

    @staticmethod
    def calculate_final_code(execution: 'PipelineExecution') -> str:
        match execution.status:
            case ExecutionStatus.SUCCESS:
                return StatusCodes.PIPELINE_FINISHED_SUCCESS
            case ExecutionStatus.FAILED:
                return StatusCodes.PIPELINE_FINISHED_FAILURE
            case _:
                return StatusCodes.PIPELINE_FINISHED_UNKNOWN

    @staticmethod
    def var_with_source(name: str, value: any, source: dict) -> dict:
        return {
            "name": name,
            "value": value,
            "source": source,
        }
