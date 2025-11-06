import json, unittest

from datetime import datetime
from pipelines_declarative_executor.model.stage import ExecutionStatus
from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from pipelines_declarative_executor.report.report_collector import ReportCollector
from pipelines_declarative_executor.utils.common_utils import CommonUtils


class TestReportCollector(unittest.TestCase):

    def test_ui_report_structure_and_field_names(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/report/pipeline_ui_report.yaml")
        pipeline_execution.pipeline.stages[0].uuid = "65ccbab8-0a07-47ab-bdf3-d0dec4b1aa07"
        pipeline_execution.pipeline.stages[0].start_time = datetime.fromisoformat("2025-05-04T12:00:00.000000")
        pipeline_execution.pipeline.stages[0].finish_time = datetime.fromisoformat("2025-05-04T12:01:11.111111")
        pipeline_execution.pipeline.stages[0].status = ExecutionStatus.SUCCESS
        pipeline_execution.pipeline.stages[0].path = "/app/quber_cli"
        # CommonUtils.write_json(ReportCollector.prepare_ui_view(pipeline_execution), "pipeline_configs/report/ui_report_sample.json")  # To regenerate expected report
        with open('pipeline_configs/report/ui_report_sample.json', 'r', encoding='utf-8') as report_file:
            expected_report = json.load(report_file)
            achieved_report = json.loads(CommonUtils.dump_json(ReportCollector.prepare_ui_view(pipeline_execution)))
            self.assertEqual(expected_report["stages"], achieved_report["stages"])
            self.assertEqual(expected_report["config"], achieved_report["config"])
            self.assertEqual(expected_report["kind"], achieved_report["kind"])
            self.assertEqual(expected_report["apiVersion"], achieved_report["apiVersion"])


if __name__ == '__main__':
    unittest.main()
