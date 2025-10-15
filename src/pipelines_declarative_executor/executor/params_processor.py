from typing import Any
from pipelines_declarative_executor.model.pipeline import PipelineVars


class ParamsProcessor:
    @staticmethod
    def _set_var(vars_storage: PipelineVars, vars_dict_name: str,
                 key: str, value: Any, source: dict, is_secure: bool) -> None:
        getattr(vars_storage, vars_dict_name)[key] = value
        vars_storage.vars_source[key] = source
        if is_secure:
            vars_storage.secure_vars.add(key)

    @staticmethod
    def file_source(source_path: str, is_remote: bool) -> dict:
        return {"kind": "REMOTE_FILE" if is_remote else "LOCAL_FILE", "path": source_path}

    @staticmethod
    def input_source(name: str) -> dict:
        return {"kind": "INPUT_VAR", "name": name}

    @staticmethod
    def set_pipeline_vars(vars_storage: PipelineVars, pipeline_vars: dict, source_path: str,
                          is_secure: bool = False, is_remote: bool = False) -> None:
        for key, value in pipeline_vars.items():
            if key not in vars_storage.vars_source:  # to avoid overwriting CONFIG vars with ones from PIPELINE
                ParamsProcessor._set_var(vars_storage, 'vars_pipeline', key, value,
                                         ParamsProcessor.file_source(source_path, is_remote), is_secure)

    @staticmethod
    def set_config_var(vars_storage: PipelineVars, key: str, value: Any, source_path: str,
                       is_secure: bool = False, is_remote: bool = False) -> None:
        ParamsProcessor._set_var(vars_storage, 'vars_config', key, value,
                                 ParamsProcessor.file_source(source_path, is_remote), is_secure)

    @staticmethod
    def set_override_var(vars_storage: PipelineVars, key: str, value: Any, is_secure: bool = False) -> None:
        ParamsProcessor._set_var(vars_storage, 'vars_override', key, value,
                                 ParamsProcessor.input_source("PIPELINE_VARS"), is_secure)

    @staticmethod
    def set_retry_var(vars_storage: PipelineVars, key: str, value: Any, is_secure: bool = False) -> None:
        ParamsProcessor._set_var(vars_storage, 'vars_retry', key, value,
                                 ParamsProcessor.input_source("RETRY_VARS"), is_secure)

    @staticmethod
    def set_global_config_var(vars_storage: PipelineVars, key: str, value: Any, source_env_key_name: str,
                              is_secure: bool = False) -> None:
        ParamsProcessor._set_var(vars_storage, 'vars_config', key, value,
                                 {"kind": "ENV_VAR_CONFIG", "name": source_env_key_name}, is_secure)

    @staticmethod
    def set_stage_output_vars(vars_storage: PipelineVars, output_params: dict, output_params_secure: dict,
                              stage_id: str, stage_uuid: str) -> None:
        source = {"kind": "STAGE", "name": stage_id, "uuid": stage_uuid}
        for key, value in output_params.items():
            ParamsProcessor._set_var(vars_storage, 'vars_stage_output', key, value, source, False)
        for key, value in output_params_secure.items():
            ParamsProcessor._set_var(vars_storage, 'vars_stage_output', key, value, source, True)
