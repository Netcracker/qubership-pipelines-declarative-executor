import sys, asyncio, click, logging

from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils


@click.group(chain=True)
def cli():
    pass


@cli.command("run")
@click.option('--pipeline_data', required=True, type=str, help="Pipeline data (pipeline/config file paths)")
@click.option('--pipeline_vars', required=False, type=str, help="Pipeline vars with high priority")
@click.option('--pipeline_dir', required=False, type=str, help="Path to directory where pipeline will be executed")
@click.option('--is_dry_run', default=False, type=bool, help="Path to directory where pipeline will be executed")
@click.option('--log_level', default='INFO', show_default=True,
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
              help="Console logging level")
def __run_pipeline(pipeline_data: str, pipeline_vars: str, pipeline_dir: str, is_dry_run: bool, log_level: str):
    setup_cli_logging(log_level)
    logging.info(f'command "RUN" with params:\npipeline_data="{pipeline_data}"\npipeline_vars="{pipeline_vars}"'
                 f'\npipeline_dir="{pipeline_dir}"\nis_dry_run="{is_dry_run}"\nlog_level="{log_level}"')
    with (LoggingUtils.time_it(), LoggingUtils.profile_it()):
        asyncio.run(create_and_run_pipeline(pipeline_data, pipeline_vars, pipeline_dir, is_dry_run))


@cli.command("retry")
@click.option('--pipeline_dir', required=True, type=str, help="Path to directory where pipeline was executed")
@click.option('--retry_vars', required=False, type=str, help="Retry vars with highest priority")
@click.option('--log_level', default='INFO', show_default=True,
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
              help="Console logging level")
def __retry_pipeline(pipeline_dir: str, retry_vars: str, log_level: str):
    setup_cli_logging(log_level)
    logging.info(f'command "RETRY" with params:\npipeline_dir="{pipeline_dir}"\nretry_vars="{retry_vars}"'
                 f'\nlog_level="{log_level}"')
    with (LoggingUtils.time_it(), LoggingUtils.profile_it()):
        asyncio.run(retry_pipeline(pipeline_dir, retry_vars))


@cli.command("archive")
@click.option('--pipeline_dir', required=True, type=str, help="Path to directory where pipeline was executed")
@click.option('--target_path', required=True, type=str, help="Path to resulting archive")
@click.option('--fail_on_missing', required=False, default=False, type=bool, help="Should this command fail if archived path is not present")
def __archive_pipeline(pipeline_dir: str, target_path: str, fail_on_missing: bool):
    setup_cli_logging()
    logging.info(f'command "ARCHIVE" with params:\npipeline_dir="{pipeline_dir}"\ntarget_path="{target_path}"')
    from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
    ArchiveUtils.archive(pipeline_dir, target_path, fail_on_missing)


@cli.command("unarchive")
@click.option('--archive_path', required=True, type=str, help="Path with archive with pipeline execution")
@click.option('--target_path', required=True, type=str, help="Path where it will be extracted")
@click.option('--fail_on_missing', required=False, default=False, type=bool, help="Should this command fail if archived path is not present")
def __unarchive_pipeline(archive_path: str, target_path: str, fail_on_missing: bool):
    setup_cli_logging()
    logging.info(f'command "UNARCHIVE" with params:\narchive_path="{archive_path}"\ntarget_path="{target_path}"')
    from pipelines_declarative_executor.utils.archive_utils import ArchiveUtils
    ArchiveUtils.unarchive(archive_path, target_path, fail_on_missing)


def setup_cli_logging(log_level: str = "INFO"):
    LoggingUtils.CONSOLE_LOG_LEVEL = getattr(logging, log_level.upper(), logging.INFO)
    LoggingUtils.configure_root_logger()
    LoggingUtils.log_env_vars()


async def create_and_run_pipeline(pipeline_data: str, pipeline_vars: str, pipeline_dir: str, is_dry_run: bool):
    from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator
    from pipelines_declarative_executor.executor.pipeline_executor import PipelineExecutor
    from pipelines_declarative_executor.report.report_uploader import ReportUploader
    from pipelines_declarative_executor.model.stage import ExecutionStatus
    try:
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution(
            pipeline_data=pipeline_data,
            pipeline_vars=pipeline_vars
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
    if EnvVar.IS_LOCAL_DEBUG:
        # local_setup()
        setup_cli_logging("DEBUG")
        logging.debug("=" * 60)
        logging.warning("RUNNING IN LOCAL DEBUG MODE!")
        with (LoggingUtils.time_it("Total time"), LoggingUtils.profile_it()):
            logging.info("Local Debug run")
            # asyncio.run(local_main_debug())
    else:
        cli()
