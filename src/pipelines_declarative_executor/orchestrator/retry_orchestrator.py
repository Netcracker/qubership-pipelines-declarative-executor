import logging
from datetime import datetime
from pathlib import Path

from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.report.report_collector import ReportCollector
from pipelines_declarative_executor.model.pipeline import PipelineExecution, PipelineVars, Pipeline
from pipelines_declarative_executor.model.stage import ExecutionStatus, StageType, Stage, When
from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.string_utils import StringUtils


class PipelineRetryOrchestrator:

    FAILED_STATUSES = [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.IN_PROGRESS]

    @staticmethod
    def prepare_retry_execution(pipeline_dir: str, retry_vars: str = None) -> PipelineExecution:
        try:
            ArchiveUtils.backup_directory(pipeline_dir, Path(pipeline_dir).joinpath(Constants.PIPELINE_BACKUP_DIR_NAME).as_posix())
        except:
            logging.error("Failed to prepare backup of execution folder")
            raise

        try:
            pipeline_state_dir = Path(pipeline_dir).joinpath(Constants.PIPELINE_STATE_DIR_NAME)
            old_execution = CommonUtils.load_json_file(pipeline_state_dir.joinpath(Constants.STATE_EXECUTION_FILE_NAME))
            old_pipeline = CommonUtils.load_json_file(pipeline_state_dir.joinpath(Constants.STATE_PIPELINE_FILE_NAME))
            old_vars = CommonUtils.load_json_file(pipeline_state_dir.joinpath(Constants.STATE_VARS_FILE_NAME))
            PipelineRetryOrchestrator._validate_execution(old_execution)
            PipelineRetryOrchestrator._validate_pipeline(old_pipeline)
            PipelineRetryOrchestrator._validate_vars(old_vars)
        except:
            logging.error("Retried pipeline directory has invalid state/file structure, impossible to retry")
            raise

        pipeline_execution = PipelineRetryOrchestrator.create_execution_from_dict(old_execution, pipeline_dir, retry_vars)

        pipeline_execution.pipeline = PipelineRetryOrchestrator.load_pipeline_from_dict(old_pipeline)
        found_failed = PipelineRetryOrchestrator._update_pipeline_state(pipeline_execution.pipeline)
        if not found_failed:
            raise Exception("Could not find any FAILED stage in retried pipeline, retry aborted!")

        vars_obj = PipelineRetryOrchestrator.load_vars_from_dict(old_vars, clear_stage_vars=True)
        if retry_vars:
            vars_list = StringUtils.trim_lines(retry_vars)
            for var in vars_list:
                if '=' in var:
                    key, value = var.split('=', 1)
                    ParamsProcessor.set_retry_var(vars_obj, key.strip(), value.strip())
        pipeline_execution.vars = vars_obj

        return pipeline_execution

    @staticmethod
    def _validate_execution(old_execution: dict):
        if not old_execution:
            raise Exception(f"{Constants.STATE_EXECUTION_FILE_NAME} in retried process is not found!")
        if StringUtils.to_bool(old_execution.get("is_dry_run")):
            raise Exception("Can't retry DRY RUN execution!") # do we care about dry-run?
        ## if old_execution.get("status") - possible status validations, but we prob should retry anyway

    @staticmethod
    def _validate_pipeline(old_pipeline: dict):
        if not old_pipeline or not old_pipeline.get("stages"):
            raise Exception(f"{Constants.STATE_PIPELINE_FILE_NAME} is missing or invalid")

    @staticmethod
    def _validate_vars(old_vars: dict):
        if not old_vars:
            raise Exception(f"{Constants.STATE_VARS_FILE_NAME} is missing or invalid")

    @staticmethod
    def create_execution_from_dict(old_execution: dict, pipeline_dir: str | Path, retry_vars: str) -> PipelineExecution:
        pipeline_execution = PipelineExecution(exec_dir=Path(pipeline_dir), is_retry=True, inputs={
            "pipeline_data": old_execution.get("inputs", {}).get("pipeline_data"),
            "pipeline_dir": pipeline_dir,
            "retry_vars": retry_vars,
            #"skip_stage": skip_stage,
        })
        # get pipeline_data from previous execution
        pipeline_execution.previous_executions = old_execution.pop("previous_executions", [])
        pipeline_execution.previous_executions.insert(0, old_execution)
        return pipeline_execution

    @staticmethod
    def load_pipeline_state_from_dir(state_dir: Path) -> PipelineExecution:
        execution_json = CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_EXECUTION_FILE_NAME))
        pipeline_json = CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_PIPELINE_FILE_NAME))
        vars_json = CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_VARS_FILE_NAME))
        pipeline_execution = PipelineExecution(**execution_json)
        if pipeline_execution.exec_dir:
            pipeline_execution.exec_dir = Path(pipeline_execution.exec_dir)
        pipeline_execution.pipeline = PipelineRetryOrchestrator.load_pipeline_from_dict(pipeline_json)
        pipeline_execution.vars = PipelineRetryOrchestrator.load_vars_from_dict(vars_json)
        return pipeline_execution

    @staticmethod
    def load_pipeline_from_dict(old_pipeline: dict) -> Pipeline:
        loaded_pipeline = Pipeline(**old_pipeline)
        loaded_pipeline.stages = []
        for stage_dict in old_pipeline.get("stages", []):
            loaded_pipeline.stages.append(PipelineRetryOrchestrator._load_stage_from_dict(stage_dict))
        return loaded_pipeline

    @staticmethod
    def load_vars_from_dict(old_vars: dict, clear_stage_vars: bool = False) -> PipelineVars:
        vars_obj = PipelineVars()
        for vars_name in ["vars_pipeline", "vars_config", "vars_override", "vars_retry",
                          "vars_stage_output", "files_info", "vars_source"]:
            setattr(vars_obj, vars_name, old_vars.get(vars_name, {}))
        vars_obj.secure_vars = set(old_vars.get("secure_vars", []))
        if clear_stage_vars:
            vars_obj.vars_stage_output.clear()
            vars_obj.files_info.clear()
        return vars_obj

    @staticmethod
    def _load_stage_from_dict(stage_dict: dict) -> Stage:
        stage = Stage(**stage_dict)
        stage.when = When(**stage_dict.get("when"))
        if stage.exec_dir:
            stage.exec_dir = Path(stage.exec_dir)
        if nested_stage_dicts := stage_dict.get("nested_parallel_stages"):
            stage.nested_parallel_stages = []
            for nested_stage in nested_stage_dicts:
                stage.nested_parallel_stages.append(PipelineRetryOrchestrator._load_stage_from_dict(nested_stage))
        if start_time := stage_dict.get("start_time"):
            stage.start_time = datetime.fromisoformat(start_time)
        if finish_time := stage_dict.get("finish_time"):
            stage.finish_time = datetime.fromisoformat(finish_time)
        return stage

    @staticmethod
    def _update_pipeline_state(pipeline: Pipeline) -> bool:
        # would be nice to collect debug info about this process, what stages we consider failed and reset
        found_failed = PipelineRetryOrchestrator._update_sequential_stages(pipeline.stages)
        return found_failed

    @staticmethod
    def _update_sequential_stages(stages: list[Stage]) -> bool:
        found_failed = False
        for stage in stages:
            found_failed = PipelineRetryOrchestrator._update_stage(stage, found_failed) or found_failed
        return found_failed

    @staticmethod
    def _update_stage(stage: Stage, found_failed: bool) -> bool:
        if stage.type == StageType.PARALLEL_BLOCK:
            found_failed = PipelineRetryOrchestrator._update_parallel_stage(stage, found_failed) or found_failed
        elif stage.type == StageType.ATLAS_PIPELINE_TRIGGER:
            found_failed = PipelineRetryOrchestrator._update_nested_stage(stage, found_failed) or found_failed
        else:
            found_failed = PipelineRetryOrchestrator._update_action_stage(stage, found_failed) or found_failed
        return found_failed

    @staticmethod
    def _update_action_stage(stage: Stage, found_failed: bool) -> bool:
        # one-action stage (python module or shell command)
        if stage.status in PipelineRetryOrchestrator.FAILED_STATUSES:
            found_failed = True
        if found_failed:
            PipelineRetryOrchestrator._reset_stage(stage)
        return found_failed

    @staticmethod
    def _update_nested_stage(stage: Stage, found_failed: bool) -> bool:
        # Nested Pipeline invoked from ours
        if found_failed:
            PipelineRetryOrchestrator._reset_stage(stage, reset_nested=True)
        else:
            found_failed_at_this_block = stage.status in PipelineRetryOrchestrator.FAILED_STATUSES
            if stage.exec_dir and found_failed_at_this_block: # we don't want to go inside if we see SUCCESS/SKIPPED, and this does it
                nested_pipeline_json_path = stage.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME).joinpath(Constants.STATE_PIPELINE_FILE_NAME)
                if nested_pipeline_json_path.exists():
                    nested_pipeline = PipelineRetryOrchestrator.load_pipeline_from_dict(CommonUtils.load_json_file(nested_pipeline_json_path))
                    found_failed_at_this_block = PipelineRetryOrchestrator._update_pipeline_state(nested_pipeline) or found_failed_at_this_block
                    CommonUtils.write_json(nested_pipeline, nested_pipeline_json_path)
                    # PipelineRetryOrchestrator._update_nested_stage_report(stage) # FOR DEBUGGING ONLY
            if found_failed_at_this_block:
                PipelineRetryOrchestrator._reset_stage(stage, reset_nested=False)
                stage.status = ExecutionStatus.IN_PROGRESS
                found_failed = found_failed_at_this_block
        return found_failed

    @staticmethod
    def _update_nested_stage_report(stage: Stage):
        # Regenerate ui_report of nested pipelines;
        # since usually it's generated at the end of pipeline processing, at each level,
        # But during Retry here we are processing our tree downwards;
        pipeline_execution = PipelineRetryOrchestrator.load_pipeline_state_from_dir(stage.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME))
        ui_view = ReportCollector.prepare_ui_view(pipeline_execution)
        CommonUtils.write_json(ui_view, pipeline_execution.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME).joinpath(Constants.PIPELINE_REPORT_FILE_NAME))

    @staticmethod
    def _update_parallel_stage(stage: Stage, found_failed: bool) -> bool:
        # PARALLEL_BLOCK with 'nested_parallel_stages' list
        if found_failed:
            PipelineRetryOrchestrator._reset_stage(stage, reset_nested=True)
        else:
            found_failed_at_this_block = stage.status in PipelineRetryOrchestrator.FAILED_STATUSES
            for nested_stage in stage.nested_parallel_stages:
                found_failed_at_this_block = PipelineRetryOrchestrator._update_stage(nested_stage, found_failed=False) or found_failed_at_this_block
            if found_failed_at_this_block:
                PipelineRetryOrchestrator._reset_stage(stage, reset_nested=False)
                found_failed = found_failed_at_this_block
        return found_failed

    @staticmethod
    def _reset_stage(stage: Stage, reset_nested: bool = False):
        stage.status = ExecutionStatus.NOT_STARTED
        stage.start_time = None
        stage.finish_time = None
        stage.evaluated_params = {}
        if reset_nested and stage.nested_parallel_stages:
            for nested in stage.nested_parallel_stages:
                PipelineRetryOrchestrator._reset_stage(nested, reset_nested=True)
