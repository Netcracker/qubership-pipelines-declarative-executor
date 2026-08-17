import json
import logging

from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.string_utils import StringUtils

STATUS_FIELDS = ("name", "status", "startedAt", "finishedAt", "progress")


class StatusProvider:
    @staticmethod
    def build_payload(execution: PipelineExecution) -> bytes | None:
        if not execution.state_dir:
            return None
        report_path = execution.state_dir.joinpath(Constants.PIPELINE_REPORT_FILE_NAME)
        if not report_path or not report_path.exists():
            logging.debug("Status delivery skipped: pipeline report is not ready yet")
            return None

        try:
            with open(report_path, "r", encoding="utf-8") as report_file:
                report = json.load(report_file)
        except Exception as e:
            logging.warning(f"Status delivery skipped: failed to read pipeline report: [{type(e)} - {str(e)}]")
            return None

        status_payload = {field: report.get(field) for field in STATUS_FIELDS if field in report}
        if "progress" not in status_payload:
            status_payload["progress"] = {"stagesTotal": 0, "stagesCompleted": 0}
        return json.dumps(status_payload, default=StringUtils.json_encode).encode("utf-8")
