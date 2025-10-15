import copy

from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import Stage, StageType
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.env_var_utils import EnvVar


class ReportCollector:
    @staticmethod
    def prepare_ui_view(execution: PipelineExecution) -> dict:
        ui_view = {
            "kind": "pipelineExecutionReport",
            "apiVersion": "v1",
            "execution": ReportCollector._prepare_execution(execution),
            "config": ReportCollector._prepare_config(execution),
            "stages": [],
        }
        for stage in execution.pipeline.stages:
            ui_view["stages"].append(ReportCollector._prepare_stage_data(stage))
        return ui_view

    @staticmethod
    def _prepare_execution(execution: PipelineExecution) -> dict:
        data = {
            "id": execution.pipeline.id,
            "name": execution.pipeline.name,
            "status": execution.status,
            "code": execution.code,
            "start_time": execution.start_time,
            "finish_time": execution.finish_time,
            "url": EnvVar.EXECUTION_URL,
            "user": EnvVar.EXECUTION_USER,
            "email": EnvVar.EXECUTION_EMAIL,
        }
        return data

    @staticmethod
    def _prepare_config(execution: PipelineExecution) -> list:
        return [
            CommonUtils.var_with_source("PIPELINE_DATA", execution.inputs.get("pipeline_data"), ParamsProcessor.input_source("CLI_INPUT")),
            CommonUtils.var_with_source("IS_DRY_RUN", execution.is_dry_run, ParamsProcessor.input_source("CLI_INPUT")),
            CommonUtils.var_with_source("IS_RETRY", execution.is_retry, ParamsProcessor.input_source("CLI_INPUT")),
            *execution.vars.initial_vars_with_sources()
        ]

    @staticmethod
    def _prepare_stage_data(stage: Stage) -> dict:
        stage_data = {"id": stage.uuid}
        for field in ["name", "path", "type", "command", "status", "start_time", "finish_time", "exec_dir", "url"]:
            stage_data[field] = getattr(stage, field, None)

        if stage.evaluated_params:
            stage_data.update(copy.deepcopy(stage.evaluated_params))
            for params_type in ["input", "output"]:
                if params_secure := stage_data.get(params_type, {}).get("params_secure", {}):
                    stage_data[params_type]["params_secure"] = ReportCollector._mask_secure_params(params_secure)

        if stage.type == StageType.PARALLEL_BLOCK:
            stage_data["nested_parallel_stages"] = []
            for nested_stage in stage.nested_parallel_stages:
                stage_data["nested_parallel_stages"].append(ReportCollector._prepare_stage_data(nested_stage))
        elif stage.type == StageType.NESTED_PIPELINE:
            stage_data["nested_pipeline"] = ReportCollector._extract_ui_view(stage)
            pass

        return stage_data

    @staticmethod
    def _mask_secure_params(data):
        if isinstance(data, dict):
            return {key: ReportCollector._mask_secure_params(value) for key, value in data.items()}
        return Constants.DEFAULT_MASKED_VALUE

    @staticmethod
    def _extract_ui_view(stage: Stage):
        if stage.exec_dir:
            nested_ui_view_path = stage.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME).joinpath(Constants.UI_VIEW_FILE_NAME)
            if nested_ui_view_path.exists():
                return CommonUtils.load_json_file(nested_ui_view_path)
        return {}

    # @staticmethod
    # def _prepare_vars(execution: PipelineExecution) -> list:
    #     return execution.vars.all_vars_with_sources()
