import os, asyncio
from datetime import datetime

from pipelines_declarative_executor.executor.condition_processor import ConditionProcessor
from pipelines_declarative_executor.executor.context_files_processor import ContextFilesProcessor
from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.executor.resource_manager import ResourceManager
from pipelines_declarative_executor.model.stage import ExecutionStatus, Stage, StageType, COMPLEX_TYPES
from pipelines_declarative_executor.model.exceptions import StageExecutionException, PipelineExecutorException
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from pipelines_declarative_executor.orchestrator.retry_orchestrator import PipelineRetryOrchestrator
from pipelines_declarative_executor.utils.color_utils import ColorUtils
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils
from pipelines_declarative_executor.utils.profiling_utils import ProfilingUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils
from pipelines_declarative_executor.x_modules_ops.dict_utils import UtilsDictionary


class StageProcessor:

    RETRY_NESTED_FLAG = "_need_to_retry_nested"

    @staticmethod
    async def process(execution: PipelineExecution, stage: Stage, parent_stage: Stage = None):

        if StageProcessor._check_retry_status(execution, stage):
            execution.logger.info(f"Skipped processing stage {stage.logged_name()} - {stage.status} (RETRY)")
            return

        is_first_run = stage.is_first_run()
        StageProcessor._pre_process(execution, stage, is_first_run)

        if not ConditionProcessor.need_to_execute(execution, stage.when):
            stage.status = ExecutionStatus.SKIPPED
            StageProcessor._post_process(execution, stage)
            return

        stage.status = ExecutionStatus.IN_PROGRESS
        execution.store_state() # just for UI realtime rendering?

        try:
            ContextFilesProcessor.prepare_stage_folder(execution, stage, parent_stage)
            if stage.type in [StageType.PYTHON_MODULE, StageType.REPORT, StageType.SHELL_COMMAND]:
                command, logged_cmd_name = StageProcessor._build_shell_command(stage)
                await StageProcessor._run_shell_command(stage, execution, command, logged_cmd_name=logged_cmd_name)
            elif stage.type == StageType.PARALLEL_BLOCK:
                await StageProcessor._run_parallel_block(execution, stage)
            elif stage.type == StageType.ATLAS_PIPELINE_TRIGGER:
                await StageProcessor._run_nested_pipeline(execution, stage)
            else:
                raise Exception(f"Unknown stage type: '{stage.type}'")

            if stage.type not in COMPLEX_TYPES:
                stage.status = ExecutionStatus.SUCCESS
                ContextFilesProcessor.store_stage_results(execution, stage)
        except asyncio.CancelledError:
            stage.status = ExecutionStatus.CANCELLED
            raise
        except Exception as e:
            stage.status = ExecutionStatus.FAILED
            execution.logger.error(f"Exception during stage {stage.logged_name()} execution: [{type(e)} - {str(e)}]")
            from pipelines_declarative_executor.executor.retry_processor import RetryProcessor
            await RetryProcessor.retry_stage(execution, stage)
            if stage.status == ExecutionStatus.FAILED:
                raise StageExecutionException(f"Stage {stage.name} failed")
        finally:
            StageProcessor._post_process(execution, stage, is_first_run)

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
    def _pre_process(execution: PipelineExecution, stage: Stage, is_first_run: bool = True):
        if is_first_run:
            stage.start_time = datetime.now()
            execution.logger.info(f"Start processing stage {stage.logged_name()}")
        else:
            execution.logger.info(f"Retry processing stage {stage.logged_name()}")

    @staticmethod
    def _post_process(execution: PipelineExecution, stage: Stage, is_first_run: bool = True):
        if not is_first_run: # only top-level process will finalize
            return
        stage.finish_time = datetime.now()
        total_time_log = f" (time: {stage.logged_time()})" if stage.type not in COMPLEX_TYPES else ""
        execution.logger.info(f"Finish processing stage {stage.logged_name()} - {stage.status}{total_time_log}")
        execution.store_state()

    @staticmethod
    def _build_shell_command(stage: Stage) -> tuple[str, str]:
        if stage.type == StageType.SHELL_COMMAND:
            command = StringUtils.normalize_line_endings(stage.evaluated_params.get('command') or "")
            logged_cmd_name = StringUtils.shorten_command(stage.command)
            if os.name == "nt":
                command = " && ".join(ln for ln in (line.strip() for line in command.split("\n")) if ln)
            else:
                command = f"set -e\n{command}"

        elif stage.type in [StageType.PYTHON_MODULE, StageType.REPORT]:
            command = (f"python {stage.path} {stage.evaluated_params.get('command')} "
                       f"--context_path={stage.exec_dir.joinpath('context.yaml')} "
                       f"--log-level={LoggingUtils.get_log_level_name()}")
            logged_cmd_name = f"{stage.path} {stage.command}"
        else:
            raise Exception(f"Invalid shell stage type - {stage.logged_name()}")
        return command, logged_cmd_name

    @staticmethod
    async def _run_shell_command(stage: Stage, execution: PipelineExecution, cmd: str, expected_return_code: int = 0,
                                 logged_cmd_name: str = "Shell Command"):
        if execution.is_dry_run:
            execution.logger.debug(f'{stage.logged_name()} - [{logged_cmd_name}] skipped in DRY RUN')
            return

        if not await ResourceManager.acquire():
            raise Exception(f"Resource acquisition timeout for stage {stage.logged_name()}")

        process, stdout, stderr, profiling_task, metrics = None, None, None, None, None
        try:
            use_cwd = stage.type == StageType.SHELL_COMMAND
            process = await asyncio.create_subprocess_shell(cmd, cwd=stage.exec_dir if use_cwd else None, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            if EnvVar.ENABLE_STAGE_RESOURCE_USAGE_PROFILING and process.pid:
                metrics = ProfilingUtils.get_profiling_metrics()
                profiling_task = asyncio.create_task(ProfilingUtils.profile_process(pid=process.pid, metrics=metrics))
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=EnvVar.SHELL_PROCESS_TIMEOUT)
            except asyncio.TimeoutError:
                if process:
                    process.kill() # instead of terminate
                    await process.wait()
                raise Exception(f"Shell command timed out after {EnvVar.SHELL_PROCESS_TIMEOUT} seconds")

        except asyncio.CancelledError:
            execution.logger.warning(f"Shell Execution cancelled! (stage {stage.logged_name()})")
            if process:
                process.kill()
                await process.wait()
            raise

        finally:
            try:
                await ResourceManager.release()
            except Exception as e:
                execution.logger.error(f"Error releasing resources: [{type(e)} - {str(e)}]")
            if EnvVar.ENABLE_STAGE_RESOURCE_USAGE_PROFILING:
                await StageProcessor._run_shell_command_finalize(stage, profiling_task, metrics)

        # Normal failure exits with a positive code, negative means our subprocess was killed by a signal - cancel case
        # Can also be a false positive due to OOM - but we can still treat that as cancellation
        if process and process.returncode is not None and process.returncode < 0:
            execution.logger.warning(f"Shell subprocess for stage {stage.logged_name()} was terminated by signal {-process.returncode} - treating as cancellation")
            raise asyncio.CancelledError

        await StageProcessor._run_shell_command_log(stage, execution, process, stdout, stderr, expected_return_code, logged_cmd_name)


    @staticmethod
    async def _run_shell_command_finalize(stage: Stage, profiling_task: asyncio.Task, metrics: dict):
        if profiling_task and not profiling_task.done():
            profiling_task.cancel()
            try:
                await profiling_task
            except asyncio.CancelledError:
                pass

        if metrics:
            if metrics['samples'] > 0:
                metrics['avg_cpu'] = metrics['total_cpu'] / metrics['samples']
            stage.custom_data.update({
                "avg_cpu": f"{metrics['avg_cpu']:.1f}%",
                "peak_memory_mb": f"{metrics['peak_memory_mb']:.1f} MB"
            })

    @staticmethod
    async def _run_shell_command_log(stage: Stage, execution: PipelineExecution, process, stdout, stderr, expected_return_code: int, logged_cmd_name: str):
        header_color = ColorUtils.SUCCESS_COLOR if process.returncode == expected_return_code else ColorUtils.FAILURE_COLOR
        header = ColorUtils.with_color(message=f" Stage Output from {stage.logged_name()}", color=header_color)
        need_to_mask_output = EnvVar.STRICT_MODE and stage.type == StageType.SHELL_COMMAND and stage.custom_data.get('command_used_secure')
        masked_output = StringUtils.indent_lines(f"{Constants.DEFAULT_MASKED_VALUE} - Shell output is masked in STRICT_MODE") if need_to_mask_output else None
        with LoggingUtils.collapsible_section(header=header, stage=stage):
            if stdout and EnvVar.ENABLE_MODULE_STDOUT_LOG:
                normalized_output = masked_output or StringUtils.indent_lines(StringUtils.normalize_line_endings(stdout.decode(errors="ignore").strip()))
                execution.logger.info(f'Shell STDOUT for {stage.logged_name()} (return_code={process.returncode}):\n{normalized_output}')
            if stderr or process.returncode != expected_return_code:
                if stderr:
                    normalized_output = masked_output or StringUtils.indent_lines(StringUtils.normalize_line_endings(stderr.decode(errors="ignore").strip()))
                    execution.logger.error(f'Shell STDERR for {stage.logged_name()} (return_code={process.returncode}):\n{normalized_output}')
                raise Exception(f"Error during {stage.logged_name()} - \"{logged_cmd_name}\"")

    @staticmethod
    async def _run_parallel_block(execution: PipelineExecution, parent_stage: Stage):
        execution.logger.info(f'Processing parallel block with multiple ({len(parent_stage.nested_parallel_stages)}) stages... (stage {parent_stage.logged_name()})')
        try:
            tasks = [StageProcessor.process(execution, nested_stage, parent_stage) for nested_stage in parent_stage.nested_parallel_stages]
            await asyncio.gather(*tasks, return_exceptions=True)
            parent_stage.status = CommonUtils.calculate_final_status(parent_stage.nested_parallel_stages)
        except asyncio.CancelledError:
            execution.logger.warning(f"Parallel block execution cancelled! (stage {parent_stage.logged_name()})")
            raise

    @staticmethod
    async def _run_nested_pipeline(execution: PipelineExecution, stage: Stage):
        try:
            execution.logger.info(f'Processing nested pipeline... (stage {stage.logged_name()})')
            input_calculated, _ = CommonUtils.calculate_dict_values(execution, stage.input)

            state_dir = stage.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME)
            if (execution.is_retry and getattr(stage, StageProcessor.RETRY_NESTED_FLAG, False)
                    and state_dir.joinpath(Constants.STATE_EXECUTION_FILE_NAME).exists()):
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
                nested_execution = PipelineOrchestrator.prepare_pipeline_execution(**StageProcessor._extract_nested_params(input_calculated))

            from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
            nested_execution = await PipelineExecutor.start(
                nested_execution,
                execution_folder_path=stage.exec_dir,
                is_dry_run=execution.is_dry_run or StringUtils.to_bool(UtilsDictionary.get_by_path(input_calculated, "params.params.IS_DRY_RUN")),
                wait_for_finish=True,
                is_nested=True,
            )
            ContextFilesProcessor.store_stage_results(execution, stage, stage.exec_dir.joinpath(Constants.PIPELINE_OUTPUT_DIR_NAME))
            stage.status = nested_execution.status
        except asyncio.CancelledError:
            execution.logger.warning("Nested pipeline execution cancelled!")
            raise

    @staticmethod
    def _extract_nested_params(params: dict) -> dict:
        return {
            'pipeline_data': (UtilsDictionary.get_by_path(params, "params.params.PIPELINE_DATA")
                              or UtilsDictionary.get_by_path(params, "params_secure.params.PIPELINE_DATA")),
            'pipeline_vars': UtilsDictionary.get_by_path(params, "params.params.PIPELINE_VARS"),
            'pipeline_vars_secure': UtilsDictionary.get_by_path(params, "params_secure.params.PIPELINE_VARS"),
        }
