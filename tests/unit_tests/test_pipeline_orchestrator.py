import unittest

from pipelines_declarative_executor.model.stage import StageType
from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator(unittest.TestCase):

    def test_pipeline_parsed_correctly(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/simple/pipeline_simple.yaml")
        self.assertEqual("Simple Pipeline", pipeline_execution.pipeline.name)
        self.assertEqual(len(pipeline_execution.pipeline.stages), 1)
        self.assertEqual(pipeline_execution.pipeline.stages[0].type, StageType.PYTHON_MODULE)
        self.assertEqual(pipeline_execution.pipeline.stages[0].command, "spam")
        self.assertEqual(pipeline_execution.vars.all_vars().get("TEST_VAR"), "test_value")


if __name__ == '__main__':
    unittest.main()
