import json, logging, unittest

from pipelines_declarative_executor.executor.condition_processor import ConditionProcessor
from pipelines_declarative_executor.model.pipeline import PipelineExecution, PipelineVars
from pipelines_declarative_executor.model.stage import When
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from common import ExecutorTestCase
with_exec_dir = ExecutorTestCase.with_exec_dir


class TestSecureSubstitution(unittest.TestCase):

    def test_calculate_expression_threads_secure_vars(self):
        pv = PipelineVars(vars_override={"TOKEN": "abc"}, secure_vars={"TOKEN"})
        self.assertEqual(pv.calculate_expression("Bearer ${TOKEN}"), ("Bearer abc", True))
        self.assertEqual(pv.calculate_expression("Bearer static"), ("Bearer static", False))

    def test_calculate_dict_values_returns_used_secure_flag(self):
        pv = PipelineVars(vars_override={"TOKEN": "abc", "SOME_CONFIG": "def"}, secure_vars={"TOKEN"})
        calculated, used_secure = CommonUtils.calculate_dict_values(None, {"params": {"URL": "h/${TOKEN}"}}, vars_obj=pv)
        self.assertTrue(used_secure)
        self.assertEqual(calculated["params"]["URL"], "h/abc")
        calculated, used_secure = CommonUtils.calculate_dict_values(None, {"params": {"URL": "$SOME_CONFIG"}}, vars_obj=pv)
        self.assertFalse(used_secure)
        self.assertEqual(calculated["params"]["URL"], "def")


class TestSecureWarnings(unittest.TestCase):

    def test_secure_var_in_condition_warns(self):
        execution = PipelineExecution(vars=PipelineVars(vars_override={"FLAG": "1"}, secure_vars={"FLAG"}))
        execution.logger = logging.getLogger("test_secure_condition")
        when = When(condition="${FLAG} == 1")
        with self.assertLogs("test_secure_condition", level=logging.DEBUG) as cm:
            result = ConditionProcessor._check_condition(execution, when)
        self.assertTrue(result)
        self.assertTrue(any(Constants.DEFAULT_MASKED_VALUE in line for line in cm.output))


class TestSecureMaskingScenario(ExecutorTestCase):

    SECRET_VALUE = "secretValue123"

    @with_exec_dir
    def test_run_secure_masking_pipeline(self):
        pipeline_data = "pipeline_configs/secure/pipeline_secure_masking.yaml"
        output = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_vars_secure=SECRET_VALUE={self.SECRET_VALUE}",
                                    f"--pipeline_dir={self.exec_dir}"])
        self.assertEqual(output.returncode, 0)

        # SHELL_COMMAND that echoes a secure var is masked - the real value never reaches the logs
        combined_output = output.stdout + output.stderr
        self.assertIn("Shell STDOUT for", combined_output)
        self.assertIn(Constants.DEFAULT_MASKED_VALUE, combined_output)
        self.assertNotIn(self.SECRET_VALUE, combined_output)

        # secure var used in pipeline/stage 'name' is replaced with the masked placeholder in the rendered name
        with open(f'{self.exec_dir}/pipeline_state/pipeline_report.json', 'r', encoding='utf-8') as report_json_file:
            report = json.load(report_json_file)
        self.assertEqual(f"Secure Masking Pipeline {Constants.DEFAULT_MASKED_VALUE}", report["name"])
        self.assertEqual(f"Secret Echo Stage {Constants.DEFAULT_MASKED_VALUE}", report["stages"][0]["name"])
        self.assertNotIn(self.SECRET_VALUE, json.dumps(report))


if __name__ == '__main__':
    unittest.main()
