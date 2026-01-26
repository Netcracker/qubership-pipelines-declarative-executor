import json
import shutil
from pathlib import Path

from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils


class DebugDataCollector:

    @staticmethod
    def collect_debug_data(execution: PipelineExecution) -> None:
        if not EnvVar.ENABLE_DEBUG_DATA_COLLECTOR:
            return

        debug_dir = Path(execution.exec_dir.joinpath(Constants.PIPELINE_DEBUG_DIR_NAME))
        if debug_dir.exists():
            shutil.rmtree(debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)

        report_path = Path(execution.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME, Constants.PIPELINE_REPORT_FILE_NAME))
        shutil.copy2(report_path, debug_dir / Constants.PIPELINE_REPORT_FILE_NAME)

        DebugDataCollector._process_stage_logs(report_path, debug_dir)

        full_log_path = Path.cwd().joinpath(LoggingUtils.FULL_EXECUTION_LOG_NAME)
        if full_log_path.exists():
            shutil.copy2(full_log_path, debug_dir)

        execution.logger.debug(f"Debug data collected at {debug_dir.as_posix()}")

    @staticmethod
    def _process_stage_logs(report_path: Path, debug_dir: Path) -> None:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        stage_logs_dir = debug_dir / Constants.DEBUG_STAGE_LOGS_DIR_NAME
        stage_logs_dir.mkdir(parents=True, exist_ok=True)
        stages = report.get('stages', [])
        DebugDataCollector._process_stages(stages, stage_logs_dir)

    @staticmethod
    def _process_stages(stages: list, stage_logs_dir: Path) -> None:
        for stage in stages:
            DebugDataCollector._process_single_stage(stage, stage_logs_dir)

            if parallel_stages := stage.get('parallelStages', []):
                DebugDataCollector._process_stages(parallel_stages, stage_logs_dir)

            if nested_stages := stage.get('nestedPipeline', {}).get('stages', []):
                DebugDataCollector._process_stages(nested_stages, stage_logs_dir)

    @staticmethod
    def _process_single_stage(stage: dict, stage_logs_dir: Path) -> None:
        exec_dir = stage.get('execDir')
        if not exec_dir:
            return

        stage_log_path = Path(exec_dir) / "logs" / "full.log"
        if stage_log_path.exists():
            target_path = stage_logs_dir / f"{stage.get('id')}.log"
            shutil.copy2(stage_log_path, target_path)
