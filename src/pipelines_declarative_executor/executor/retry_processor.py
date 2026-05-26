import asyncio

from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import Stage, ExecutionStatus, COMPLEX_TYPES
from pipelines_declarative_executor.report.report_collector import ReportCollector
from pipelines_declarative_executor.utils.string_utils import StringUtils


class RetryProcessor:

    DEFAULT_LIMIT = "5"
    DEFAULT_FACTOR = "2"
    DEFAULT_DURATION = "5s"

    @staticmethod
    async def retry_stage(execution: PipelineExecution, stage: Stage):
        try:
            retry_config = stage.evaluated_params.get('retry')
            if retry_config is None or stage.status != ExecutionStatus.FAILED or stage.type in COMPLEX_TYPES or execution.is_dry_run:
                return

            attempt = stage.custom_data.get("retry_attempt", 0) + 1
            limit = int(retry_config.get("limit", RetryProcessor.DEFAULT_LIMIT))
            if limit != -1 and attempt > limit:
                execution.logger.info(f"Stage {stage.logged_name()} reached retry attempts limit (limit={limit})")
                return

            stage.custom_data["retry_attempt"] = attempt
            try:
                timeout = RetryProcessor._calc_timeout(retry_config, attempt)
            except Exception as e:
                execution.logger.error(f"Exception during stage {stage.logged_name()} retry-configuration parsing: [{type(e)} - {str(e)}] - retry is aborted")
                return

            stage.status = ExecutionStatus.NOT_STARTED  # avoid affecting other stages when.condition
            execution.logger.warning(f"Stage {stage.logged_name()} - retry #{attempt} in {timeout}s (limit: {limit})")
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            stage.status = ExecutionStatus.CANCELLED
            raise

        from pipelines_declarative_executor.executor.stage_processor import StageProcessor
        await StageProcessor.process(execution, stage)

    @staticmethod
    async def retry_pipeline_execution(execution: PipelineExecution):
        retry_config = execution.pipeline.configuration.get('retry')
        if retry_config is None or execution.status != ExecutionStatus.FAILED or execution.is_dry_run:
            return

        attempt = execution.custom_data.get("retry_attempt", 0) + 1
        limit = int(retry_config.get("limit", RetryProcessor.DEFAULT_LIMIT))
        if limit != -1 and attempt > limit:
            execution.logger.info(f"Pipeline Execution reached retry attempts limit (limit={limit})")
            return

        try:
            timeout = RetryProcessor._calc_timeout(retry_config, attempt)
        except Exception as e:
            execution.logger.error(f"Exception during Pipeline retry-configuration parsing: [{type(e)} - {str(e)}] - retry is aborted")
            return

        retry_msg = f"Pipeline Retry #{attempt} in {timeout}s (limit: {limit}) - {execution.pipeline.logged_name()}"
        execution.logger.warning("\n" + StringUtils.format_pipeline_header(retry_msg))
        await asyncio.sleep(timeout)

        from pipelines_declarative_executor.orchestrator.retry_orchestrator import PipelineRetryOrchestrator
        from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
        execution = PipelineRetryOrchestrator.prepare_retry_execution(pipeline_dir=execution.exec_dir, existing_execution=execution)
        original_start_time = execution.start_time
        execution.custom_data["retry_attempt"] = attempt
        ReportCollector.reset_stages_cache(execution=execution)

        await PipelineExecutor.start(
            execution=execution,
            execution_folder_path=execution.exec_dir,
            is_dry_run=execution.is_dry_run,
            wait_for_finish=True,
            is_nested=execution.is_nested,
            suppress_summary=True,
        )
        execution.start_time = original_start_time

    @staticmethod
    def _calc_timeout(retry_config: dict, attempt: int) -> float:
        factor = int(retry_config.get("backoff", {}).get("factor", RetryProcessor.DEFAULT_FACTOR))
        duration = retry_config.get("backoff", {}).get("duration", RetryProcessor.DEFAULT_DURATION)
        timeout = StringUtils.duration_str_to_seconds(duration) * (factor ** (attempt - 1))
        if max_duration := retry_config.get("backoff", {}).get("max_duration"):
            timeout = min(timeout, StringUtils.duration_str_to_seconds(max_duration))
        return timeout
