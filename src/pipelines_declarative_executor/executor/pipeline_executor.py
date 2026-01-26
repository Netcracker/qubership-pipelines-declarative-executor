import asyncio, tempfile

from datetime import datetime
from pathlib import Path

from pipelines_declarative_executor.executor.context_files_processor import ContextFilesProcessor
from pipelines_declarative_executor.executor.stage_processor import StageProcessor
from pipelines_declarative_executor.model.stage import ExecutionStatus
from pipelines_declarative_executor.model.exceptions import StageExecutionException
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.report.report_summary_table import ReportSummaryTable
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.debug_data_collector import DebugDataCollector
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils


class PipelineExecutor:
    @staticmethod
    async def start(execution: PipelineExecution,
                    execution_folder_path: str | Path,
                    is_dry_run: bool = False,
                    wait_for_finish: bool = False,
                    is_nested: bool = False) -> PipelineExecution:
        if not execution.is_retry:
            if not execution_folder_path:
                execution.exec_dir = Path(tempfile.mkdtemp())
            else:
                execution.exec_dir = CommonUtils.create_exec_dir(execution_folder_path)
            execution.is_dry_run = is_dry_run
        execution.logger = LoggingUtils.configure_logger(execution.exec_dir)
        execution.logger.info(f"Execution directory: {execution.exec_dir.absolute().as_posix()}")
        execution.exec_process = asyncio.create_task(PipelineExecutor._process(execution))
        execution.is_nested = is_nested
        if wait_for_finish:
            await execution.exec_process
        return execution

    @staticmethod
    async def _process(execution: PipelineExecution) -> PipelineExecution:
        try:
            PipelineExecutor._execution_start(execution)
            for stage in execution.pipeline.stages:
                try:
                    await StageProcessor.process(execution, stage)
                except StageExecutionException:
                    pass
            ContextFilesProcessor.store_pipeline_results(execution)
        except asyncio.CancelledError:
            execution.logger.warning("Stages processing cancelled!")
        except Exception as e:
            execution.logger.error(f"Something went wrong during Pipeline execution: [{type(e)} - {str(e)}]")
        finally:
            PipelineExecutor._execution_finish(execution)
            return execution

    @staticmethod
    def _execution_start(execution: PipelineExecution):
        execution.logger.info(f"Pipeline {execution.pipeline.logged_name()} execution started!"
                              f"{' (DRY RUN)' if execution.is_dry_run else ''}"
                              f"{' (RETRY)' if execution.is_retry else ''}")
        execution.status = ExecutionStatus.IN_PROGRESS
        execution.start_time = datetime.now()
        execution.store_state()

    @staticmethod
    def _execution_finish(execution: PipelineExecution):
        execution.status = CommonUtils.calculate_final_status(execution.pipeline.stages)
        execution.code = CommonUtils.calculate_final_code(execution)
        execution.finish_time = datetime.now()
        execution.store_state()
        execution.logger.info(f"Pipeline {execution.pipeline.logged_name()} execution finished - {execution.status}")
        if not execution.is_nested:
            execution.logger.info(f"\n{ReportSummaryTable.generate_summary_table(execution=execution)}")
            DebugDataCollector.collect_debug_data(execution=execution)
        execution.logger.handlers.clear() # clean up Logger
