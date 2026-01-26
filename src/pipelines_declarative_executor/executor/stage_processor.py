import asyncio
from datetime import datetime

from pipelines_declarative_executor.executor.condition_processor import ConditionProcessor
from pipelines_declarative_executor.executor.context_files_processor import ContextFilesProcessor
from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.stage import ExecutionStatus, Stage, StageType, COMPLEX_TYPES
from pipelines_declarative_executor.model.exceptions import StageExecutionException, PipelineExecutorException
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from pipelines_declarative_executor.orchestrator.retry_orchestrator import PipelineRetryOrchestrator
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


class StageProcessor:

    RETRY_NESTED_FLAG = "_need_to_retry_nested"

    @staticmethod
    async def process(execution: PipelineExecution, stage: Stage, parent_stage: Stage = None):

        if StageProcessor._check_retry_status(execution, stage):
            execution.logger.info(f"Skipped processing stage {stage.logged_name()} - {stage.status} (RETRY)")
            return

        StageProcessor._pre_process(execution, stage)

        if not ConditionProcessor.need_to_execute(execution, stage.when):
            stage.status = ExecutionStatus.SKIPPED
            StageProcessor._post_process(execution, stage)
            return

        stage.status = ExecutionStatus.IN_PROGRESS
        execution.store_state() # just for UI realtime rendering?

        try:
            shell_timer, store_results_timer = None, None
            with LoggingUtils.Timer() as prepare_files_timer:
                ContextFilesProcessor.prepare_stage_folder(execution, stage, parent_stage)

            if stage.type in [StageType.PYTHON_MODULE, StageType.REPORT]:
                command = (f"python {stage.path} {stage.command} "
                           f"--context_path={stage.exec_dir.joinpath('context.yaml')} "
                           f"--log-level={LoggingUtils.get_log_level_name()}")
                with LoggingUtils.Timer() as shell_timer:
                    await StageProcessor._run_shell_command(stage, execution, command, logged_cmd_name=f"{stage.path} {stage.command}")
            elif stage.type == StageType.SHELL_COMMAND:
                await StageProcessor._run_shell_command(stage, execution, stage.command, logged_cmd_name=stage.command)
            elif stage.type == StageType.PARALLEL_BLOCK:
                await StageProcessor._run_parallel_block(execution, stage)
            elif stage.type == StageType.ATLAS_PIPELINE_TRIGGER:
                await StageProcessor._run_nested_pipeline(execution, stage)
            else:
                raise Exception(f"Unknown stage type: '{stage.type}'")

            if stage.type not in COMPLEX_TYPES:
                stage.status = ExecutionStatus.SUCCESS
                with LoggingUtils.Timer() as store_results_timer:
                    ContextFilesProcessor.store_stage_results(execution, stage)
        except asyncio.CancelledError:
            stage.status = ExecutionStatus.CANCELLED
            raise
        except Exception as e:
            stage.status = ExecutionStatus.FAILED
            execution.logger.error(f"Something went wrong during stage {stage.logged_name()} execution: [{type(e)} - {str(e)}]")
            raise StageExecutionException(f"Stage {stage.name} failed")
        finally:
            StageProcessor._post_process(execution, stage)
            if stage.type in [StageType.PYTHON_MODULE, StageType.REPORT] and EnvVar.ENABLE_PROFILER_STATS:
                if shell_timer and prepare_files_timer and store_results_timer:
                    execution.logger.debug(
                        f"{stage.logged_name()} - "
                        f"total stage time: {(stage.finish_time - stage.start_time).total_seconds() * 1000:.0f} ms, "
                        f"CLI execution: {shell_timer.elapsed_time_ms:.0f} ms, "
                        f"prepare files: {prepare_files_timer.elapsed_time_ms:.0f} ms, "
                        f"store results: {store_results_timer.elapsed_time_ms:.0f} ms"
                    )

    @staticmethod
    def _check_retry_status(execution: PipelineExecution, stage: Stage) -> bool:
        if not execution.is_retry or stage.status == ExecutionStatus.NOT_STARTED:
            return False

        if stage.status in [ExecutionStatus.SUCCESS, ExecutionStatus.SKIPPED]:
            ContextFilesProcessor.store_retried_stage_results(execution, stage)
            return True

        if stage.type == StageType.ATLAS_PIPELINE_TRIGGER and stage.status == ExecutionStatus.IN_PROGRESS:
            setattr(stage, StageProcessor.RETRY_NESTED_FLAG, True)
            return False

        raise PipelineExecutorException(
            "Unexpected status/stage-type combination during pipeline RETRY:"
            f" {stage.logged_name()} - {stage.status} - {stage.type}"
        )

    @staticmethod
    def _pre_process(execution: PipelineExecution, stage: Stage):
        stage.start_time = datetime.now()
        execution.logger.info(f"Start processing stage {stage.logged_name()}")

    @staticmethod
    def _post_process(execution: PipelineExecution, stage: Stage):
        stage.finish_time = datetime.now()
        execution.logger.info(f"Finish processing stage {stage.logged_name()} - {stage.status}")
        execution.store_state()

    @staticmethod
    async def _run_shell_command(stage: Stage, execution: PipelineExecution, cmd: str, expected_return_code: int = 0,
                                 logged_cmd_name: str = "Shell Command"):
        if execution.is_dry_run:
            execution.logger.debug(f'{stage.logged_name()} - [{logged_cmd_name}] skipped in DRY RUN')
            return
        process = None
        timeout = EnvVar.SHELL_PROCESS_TIMEOUT
        try:
            process = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.PIPE)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                if process:
                    process.kill() # instead of terminate
                raise Exception(f"Shell command timed out after {timeout} seconds")
        except asyncio.CancelledError:
            execution.logger.warning(f"Shell Execution cancelled! (stage {stage.logged_name()})")
            if process:
                process.terminate()
            raise
        execution.logger.debug(f'{stage.logged_name()} - [{logged_cmd_name}] finished with return_code={process.returncode}')
        if stdout and EnvVar.ENABLE_MODULE_STDOUT_LOG:
            normalized_output = StringUtils.normalize_line_endings(stdout.decode(errors="ignore").strip())
            execution.logger.info(f'Shell STDOUT for {stage.logged_name()}:\n{normalized_output}')
        if stderr or process.returncode != expected_return_code:
            if stderr:
                normalized_output = StringUtils.normalize_line_endings(stderr.decode(errors="ignore").strip())
                execution.logger.error(f'Shell STDERR for {stage.logged_name()}:\n{normalized_output}')
            raise Exception(f"Error during {stage.logged_name()} - \"{logged_cmd_name}\"")

    @staticmethod
    async def _run_parallel_block(execution: PipelineExecution, parent_stage: Stage):
        execution.logger.info(f'Processing parallel block with multiple ({len(parent_stage.nested_parallel_stages)}) stages... (stage {parent_stage.logged_name()})')
        try:
            semaphore = asyncio.Semaphore(EnvVar.MAX_CONCURRENT_STAGES)
            async def process_with_semaphore(stage):
                async with semaphore:
                    return await StageProcessor.process(execution, stage, parent_stage)

            tasks = [process_with_semaphore(nested_stage) for nested_stage in parent_stage.nested_parallel_stages]
            await asyncio.gather(*tasks, return_exceptions=True)
            parent_stage.status = CommonUtils.calculate_final_status(parent_stage.nested_parallel_stages)
        except asyncio.CancelledError:
            execution.logger.warning(f"Parallel block execution cancelled! (stage {parent_stage.logged_name()})")
            raise

    @staticmethod
    async def _run_nested_pipeline(execution: PipelineExecution, stage: Stage):
        try:
            execution.logger.info(f'Processing nested pipeline... (stage {stage.logged_name()})')
            input_calculated = CommonUtils.calculate_dict_values(execution, stage.input)

            if execution.is_retry and getattr(stage, StageProcessor.RETRY_NESTED_FLAG, False):
                state_dir = stage.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME)
                nested_execution = PipelineRetryOrchestrator.create_execution_from_dict(
                    CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_EXECUTION_FILE_NAME)),
                    stage.exec_dir, execution.inputs.get("retry_vars")
                )
                nested_execution.pipeline = PipelineRetryOrchestrator.load_pipeline_from_dict(
                    CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_PIPELINE_FILE_NAME))
                )
                nested_execution.vars = PipelineRetryOrchestrator.load_vars_from_dict(
                    CommonUtils.load_json_file(state_dir.joinpath(Constants.STATE_VARS_FILE_NAME)), clear_stage_vars=True
                )
                for key, value in execution.vars.vars_retry.items():
                    ParamsProcessor.set_retry_var(nested_execution.vars, key, value)
            else:
                nested_execution = PipelineOrchestrator.prepare_pipeline_execution(
                    input_calculated.get('pipeline_data'),
                    input_calculated.get('pipeline_vars')
                )

            from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
            await PipelineExecutor.start(
                nested_execution,
                execution_folder_path=stage.exec_dir,
                is_dry_run=execution.is_dry_run or StringUtils.to_bool(input_calculated.get('is_dry_run')),
                wait_for_finish=True,
                is_nested=True,
            )
            ContextFilesProcessor.store_stage_results(execution, stage, stage.exec_dir.joinpath(Constants.PIPELINE_OUTPUT_DIR_NAME))
            stage.status = nested_execution.status
        except asyncio.CancelledError:
            execution.logger.warning("Nested pipeline execution cancelled!")
            raise
