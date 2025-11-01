import copy

from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import Stage, StageType
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.string_utils import StringUtils


class ReportCollector:

    NESTED_PIPELINE = "nestedPipeline"
    PARALLEL_STAGES = "parallelStages"

    @staticmethod
    def prepare_ui_view(execution: PipelineExecution) -> dict:
        ui_view = {
            "kind": "AtlasPipelineReport",
            "apiVersion": "v2",
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
            "startedAt": execution.start_time,
            "finishedAt": execution.finish_time,
            "time": StringUtils.get_duration_str(execution.start_time, execution.finish_time),
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
        for field_mapping in ["name", "path", "type", "command", "status", ("start_time", "startedAt"),
                              ("finish_time", "finishedAt"), "time", ("exec_dir", "execDir"), "url"]:
            model_field, report_field = field_mapping if isinstance(field_mapping, tuple) else (field_mapping, field_mapping)
            stage_data[report_field] = getattr(stage, model_field, None)
        stage_data["time"] = StringUtils.get_duration_str(stage.start_time, stage.finish_time)

        if stage.evaluated_params:
            stage_data.update(copy.deepcopy(stage.evaluated_params))
            for params_type in ["input", "output"]:
                if params_secure := stage_data.get(params_type, {}).get("params_secure", {}):
                    stage_data[params_type]["params_secure"] = ReportCollector._mask_secure_params(params_secure)

        if stage.type == StageType.PARALLEL_BLOCK:
            stage_data[ReportCollector.PARALLEL_STAGES] = []
            for nested_stage in stage.nested_parallel_stages:
                stage_data[ReportCollector.PARALLEL_STAGES].append(ReportCollector._prepare_stage_data(nested_stage))
        elif stage.type == StageType.ATLAS_PIPELINE_TRIGGER:
            stage_data[ReportCollector.NESTED_PIPELINE] = ReportCollector._extract_ui_view(stage)

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
