import sys, asyncio, click, logging, signal

from pipelines_declarative_executor.utils.common_setup import CommonSetup
from pipelines_declarative_executor.utils.profiling_utils import ProfilingUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


@click.group(chain=True)
def cli():
    pass


@cli.command("run")
@click.option('--pipeline_data', required=True, type=str, help="Pipeline data (pipeline/config file paths)")
@click.option('--pipeline_vars', required=False, type=str, help="Pipeline vars with high priority")
@click.option('--pipeline_vars_secure', required=False, type=str, help="Secure pipeline vars with high priority that are masked in logs/report")
@click.option('--pipeline_dir', required=False, type=str, help="Path to directory where pipeline will be executed")
@click.option('--is_dry_run', default=False, type=bool, help="Dry run mode (no actual execution)")
@click.option('--log_level', default='INFO', show_default=True,
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
              help="Console logging level")
def __run_pipeline(pipeline_data: str, pipeline_vars: str, pipeline_vars_secure: str, pipeline_dir: str, is_dry_run: bool, log_level: str):
    CommonSetup.setup_cli(log_level=log_level)
    logging.info(
        f'command "RUN" with params:'
        f'\n{format_param("PIPELINE_DATA", pipeline_data)}'
        f'\n{format_pipeline_vars(pipeline_vars, pipeline_vars_secure)}'
        f'\nPIPELINE_DIR="{pipeline_dir}"\nIS_DRY_RUN="{is_dry_run}"\nLOG_LEVEL="{log_level}"'
    )
    with (ProfilingUtils.time_it(), ProfilingUtils.profile_it(), ProfilingUtils.track_peak_usage()):
        asyncio.run(create_and_run_pipeline(pipeline_data, pipeline_vars, pipeline_vars_secure, pipeline_dir, is_dry_run))


@cli.command("retry")
@click.option('--pipeline_dir', required=True, type=str, help="Path to directory where pipeline was executed")
@click.option('--retry_vars', required=False, type=str, help="Retry vars with highest priority")
@click.option('--log_level', default='INFO', show_default=True,
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
              help="Console logging level")
def __retry_pipeline(pipeline_dir: str, retry_vars: str, log_level: str):
    CommonSetup.setup_cli(log_level=log_level)
    logging.info(f'command "RETRY" with params:\nPIPELINE_DIR="{pipeline_dir}"\n{format_param("RETRY_VARS", retry_vars)}'
                 f'\nLOG_LEVEL="{log_level}"')
    with (ProfilingUtils.time_it(), ProfilingUtils.profile_it(), ProfilingUtils.track_peak_usage()):
        asyncio.run(retry_pipeline(pipeline_dir, retry_vars))


@cli.command("archive")
@click.option('--pipeline_dir', required=True, type=str, help="Path to directory where pipeline was executed")
@click.option('--target_path', required=True, type=str, help="Path to resulting archive")
@click.option('--fail_on_missing', required=False, default=False, type=bool, help="Should this command fail if archived path is not present")
def __archive_pipeline(pipeline_dir: str, target_path: str, fail_on_missing: bool):
    CommonSetup.setup_cli(log_env_vars=False)
    logging.info(f'command "ARCHIVE" with params:\nPIPELINE_DIR="{pipeline_dir}"\nTARGET_PATH="{target_path}"')
    from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
    ArchiveUtils.archive(pipeline_dir, target_path, fail_on_missing, use_sops_key=True)


@cli.command("unarchive")
@click.option('--archive_path', required=True, type=str, help="Path with archive with pipeline execution")
@click.option('--target_path', required=True, type=str, help="Path where it will be extracted")
@click.option('--fail_on_missing', required=False, default=False, type=bool, help="Should this command fail if archived path is not present")
def __unarchive_pipeline(archive_path: str, target_path: str, fail_on_missing: bool):
    CommonSetup.setup_cli(log_env_vars=False)
    logging.info(f'command "UNARCHIVE" with params:\nARCHIVE_PATH="{archive_path}"\nTARGET_PATH="{target_path}"')
    from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
    ArchiveUtils.unarchive(archive_path, target_path, fail_on_missing, use_sops_key=True)


def format_param(name: str, value: str | None) -> str:
    if value:
        items = StringUtils.trim_lines(value)
        if items:
            return f"{name}:\n" + "\n".join(f"   {item}" for item in items)
    return f"{name}: None"


def format_pipeline_vars(pipeline_vars: str | None, pipeline_vars_secure: str | None) -> str:
    formatted_vars = []
    if pipeline_vars:
        for item in StringUtils.trim_lines(pipeline_vars):
            formatted_vars.append(f"   {item}")
    if pipeline_vars_secure:
        for item in StringUtils.trim_lines(pipeline_vars_secure):
            if '=' in item:
                key, value = item.split('=', 1)
                formatted_vars.append(f"   {key.strip()}={StringUtils.mask_value(value=value)}")
    if formatted_vars:
        return "PIPELINE_VARS:\n" + "\n".join(formatted_vars)
    return "PIPELINE_VARS: None"


def install_cancellation_handlers():
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    def _cancel(signame: str):
        logging.warning(f"Received {signame} - cancelling pipeline execution...")
        main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _cancel, sig.name)
        except (NotImplementedError, RuntimeError):
            pass


async def create_and_run_pipeline(pipeline_data: str, pipeline_vars: str, pipeline_vars_secure: str, pipeline_dir: str, is_dry_run: bool):
    from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator
    from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
    from pipelines_declarative_executor.report.report_uploader import ReportUploader
    from pipelines_declarative_executor.model.stage import ExecutionStatus
    install_cancellation_handlers()
    try:
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution(
            pipeline_data=pipeline_data,
            pipeline_vars=pipeline_vars,
            pipeline_vars_secure=pipeline_vars_secure,
        )
    except Exception as e:
        logging.error(f"Exception during orchestration: {e}")
        sys.exit(1)
    async with ReportUploader(execution=pipeline_execution, configs=ReportUploader.load_endpoint_configs()):
        await PipelineExecutor.start(
            execution=pipeline_execution,
            execution_folder_path=pipeline_dir,
            is_dry_run=is_dry_run,
            wait_for_finish=True,
        )
    if pipeline_execution.status != ExecutionStatus.SUCCESS:
        sys.exit(1)


async def retry_pipeline(pipeline_dir: str, retry_vars: str):
    from pipelines_declarative_executor.orchestrator.retry_orchestrator import PipelineRetryOrchestrator
    from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
    from pipelines_declarative_executor.report.report_uploader import ReportUploader
    from pipelines_declarative_executor.model.stage import ExecutionStatus
    install_cancellation_handlers()
    try:
        pipeline_execution = PipelineRetryOrchestrator.prepare_retry_execution(
            pipeline_dir=pipeline_dir,
            retry_vars=retry_vars,
        )
    except Exception as e:
        logging.error(f"Exception during orchestration: {e}")
        sys.exit(1)
    async with ReportUploader(execution=pipeline_execution, configs=ReportUploader.load_endpoint_configs()):
        await PipelineExecutor.start(
            execution=pipeline_execution,
            execution_folder_path=pipeline_dir,
            is_dry_run=pipeline_execution.is_dry_run,
            wait_for_finish=True,
        )
    if pipeline_execution.status != ExecutionStatus.SUCCESS:
        sys.exit(1)


if __name__ == '__main__':
    cli()
