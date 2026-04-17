import os
import unittest
from unittest.mock import patch

from pipelines_declarative_executor.model.stage import StageType, ExecutionStatus
from pipelines_declarative_executor.orchestrator.pipeline_orchestrator import PipelineOrchestrator


class TestPipelineOrchestrator(unittest.TestCase):

    def test_simple_pipeline_parsed_correctly(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/simple/pipeline_simple.yaml")
        self.assertEqual("Simple Pipeline", pipeline_execution.pipeline.name)
        self.assertEqual(len(pipeline_execution.pipeline.stages), 1)
        self.assertEqual(pipeline_execution.pipeline.stages[0].type, StageType.PYTHON_MODULE)
        self.assertEqual(pipeline_execution.pipeline.stages[0].command, "spam")
        self.assertEqual(pipeline_execution.vars.all_vars().get("TEST_VAR"), "test_value")

    def test_parallel_list_syntax(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/syntax/parallel_list.yaml")
        self.assertEqual(len(pipeline_execution.pipeline.stages), 1)
        self.assertEqual(len(pipeline_execution.pipeline.stages[0].nested_parallel_stages), 3)

    def test_parallel_dict_syntax(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/syntax/parallel_dict.yaml")
        self.assertEqual(len(pipeline_execution.pipeline.stages), 1)
        self.assertEqual(len(pipeline_execution.pipeline.stages[0].nested_parallel_stages), 3)

    def test_when_syntax(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/syntax/when_conditions.yaml")
        self.assertEqual(pipeline_execution.pipeline.stages[0].when.condition, "INPUT_KEYWORD in ['list', 'of', 'correct', 'words']")
        self.assertEqual(pipeline_execution.pipeline.stages[1].when.statuses, [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED])
        self.assertEqual(pipeline_execution.pipeline.stages[2].when.condition, "INPUT_KEYWORD == 'correct'")
        self.assertEqual(pipeline_execution.pipeline.stages[2].when.statuses, [ExecutionStatus.FAILED])

    def test_stages_inside_stages_syntax(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/syntax/stages_inside_stages.yaml")
        self.assertEqual(len(pipeline_execution.pipeline.stages), 5)
        self.assertEqual(len(pipeline_execution.pipeline.stages[4].nested_parallel_stages), 4)

    def test_global_config_vars_parsed_correctly(self):
        with open('pipeline_configs/calc/config_calculator.yaml', 'r') as f:
            global_config_content = f.read()
        with patch.dict(os.environ, {'CUSTOM_GLOBAL_CONFIG_1': global_config_content}):
            pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/simple/pipeline_simple.yaml")
            self.assertEqual(pipeline_execution.vars.all_vars().get("STAGE_TYPE_PY"), "PYTHON_MODULE")
            self.assertEqual(pipeline_execution.vars.all_vars().get("CALC_ARG1"), 9)
            self.assertEqual(pipeline_execution.vars.all_vars().get("CALC_ARG2"), 10)

if __name__ == '__main__':
    unittest.main()
