import logging

from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.utils.constants import Constants


class ReportProvider:
    @staticmethod
    def build_payload(execution: PipelineExecution) -> bytes | None:
        if not execution.state_dir:
            return None
        report_path = execution.state_dir.joinpath(Constants.PIPELINE_REPORT_FILE_NAME)
        if not report_path or not report_path.exists():
            logging.debug("Report delivery skipped: pipeline report is not ready yet")
            return None
        try:
            return report_path.read_bytes()
        except Exception as e:
            logging.warning(f"Report delivery skipped: failed to read pipeline report: [{type(e)} - {str(e)}]")
            return None
