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

    def test_pipeline_data_load_order(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution("pipeline_configs/syntax/stages_inside_stages.yaml;pipeline_configs/simple/pipeline_simple.yaml")
        self.assertEqual("Simple Pipeline", pipeline_execution.pipeline.name)
        self.assertEqual(len(pipeline_execution.pipeline.stages), 1)

    def test_templates_order_priority(self):
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution(
            "pipeline_configs/simple/config_simple.yaml;"
            "pipeline_configs/templates/common_jobs_template.yaml;"
            "pipeline_configs/templates/test_template.yaml;"
            "pipeline_configs/templates/pipeline_using_templates.yaml;"
        )

        # pipeline.vars merge test
        self.assertEqual(pipeline_execution.vars.all_vars().get("TEST_PIPELINE_VAR"), "value_from_pipeline")
        self.assertEqual(pipeline_execution.vars.all_vars().get("TEST_TEMPLATE_VAR"), "value_from_template2")
        self.assertEqual(pipeline_execution.vars.all_vars().get("VAR_FROM_SIMPLE_CONFIG"), 56)

        # pipeline.jobs merge test
        self.assertEqual(len(pipeline_execution.pipeline.stages), 3)
        self.assertEqual(pipeline_execution.pipeline.stages[0].input.get("params", {}).get("params", {}).get("some_param_from_pipeline"), True)
        self.assertEqual(pipeline_execution.pipeline.stages[1].input.get("params", {}).get("params", {}).get("some_param_from_template2"), True)
        self.assertEqual(pipeline_execution.pipeline.stages[1].input.get("params", {}).get("params", {}).get("some_param_from_template1"), None)
        self.assertEqual(pipeline_execution.pipeline.stages[2].input.get("params", {}).get("params", {}).get("some_param_from_template2"), True)

        # pipeline.configuration merge test
        self.assertEqual(pipeline_execution.pipeline.configuration.get("retry", {}).get("limit"), 5)
        self.assertEqual(pipeline_execution.pipeline.configuration.get("output", {}).get("params", {}).get("params", {}).get("RESULT_SPAM"), "${RESULT_SPAM}")
        self.assertEqual(pipeline_execution.pipeline.configuration.get("output", {}).get("params", {}).get("params", {}).get("RESULT_SPAMUS"), None)

    def test_pipeline_vars_and_secure_vars_parsed_correctly(self):
        pipeline_vars = "OVER_PARAM_1 = 123\nOVER_PARAM_2 = 456"
        secure_vars = "SECRET_TOKEN = s3cr3t\nHIDE_IT = hidden_value"
        pipeline_execution = PipelineOrchestrator.prepare_pipeline_execution(
            "pipeline_configs/simple/pipeline_simple.yaml",
            pipeline_vars=pipeline_vars,
            pipeline_vars_secure=secure_vars,
        )
        self.assertEqual(pipeline_execution.vars.all_vars().get("TEST_VAR"), "test_value")
        self.assertEqual(pipeline_execution.vars.all_vars().get("OVER_PARAM_1"), "123")
        self.assertEqual(pipeline_execution.vars.all_vars().get("OVER_PARAM_2"), "456")
        self.assertEqual(pipeline_execution.vars.all_vars().get("SECRET_TOKEN"), "s3cr3t")
        self.assertEqual(pipeline_execution.vars.all_vars().get("HIDE_IT"), "hidden_value")
        self.assertIn("SECRET_TOKEN", pipeline_execution.vars.secure_vars)
        self.assertNotIn("OVER_PARAM_1", pipeline_execution.vars.secure_vars)


if __name__ == '__main__':
    unittest.main()
