import os, re, yaml, logging, unittest, time

from common import ExecutorTestCase


#@unittest.skip("skipping...")
class TestPipelinesDeclarativeExecutor(ExecutorTestCase):

    PDE_CLI = ["python", "-m", "pipelines_declarative_executor"]

    def setUp(self):
        logging.info(os.getcwd())

    def test_help_option(self):
        output = self._run_and_log([*self.PDE_CLI, "--help"])
        self.assertTrue("Commands:" in output.stdout + output.stderr)

    def test_run_no_pipeline_found(self):
        output = self._run_and_log([*self.PDE_CLI, "run", "--pipeline_data='non_existent.yaml'"])
        self.assertTrue("No 'AtlasPipeline' present in 'pipeline_data'" in output.stdout + output.stderr)

    def test_run_remote_file(self):
        exec_dir = "/simple_pipeline_exec_dir"
        pipeline_data = "https://raw.githubusercontent.com/Netcracker/qubership-pipelines-declarative-executor/refs/heads/main/tests/pipeline_configs/simple/pipeline_simple.yaml"
        output = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_dir={exec_dir}"])
        self.assertEqual(output.returncode, 0)

    def test_run_calculator_pipeline(self):
        exec_dir = "/calculator_pipeline_exec_dir"
        pipeline_data = "pipeline_configs/calc/config_calculator.yaml;pipeline_configs/calc/pipeline_calculator.yaml;"
        output = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_dir={exec_dir}"])
        self.assertEqual(output.returncode, 0)
        with open(f'{exec_dir}/pipeline_output/output_params.yaml', 'r', encoding='utf-8') as file:
            result = yaml.safe_load(file)
            self.assertEqual('19',  result['params']['CALC_RESULT'])
        with open(f'{exec_dir}/pipeline_output/output_params_secure.yaml', 'r') as secure_file:
            from pipelines_declarative_executor.utils.sops_utils import SopsUtils
            yaml_dict, is_encrypted = SopsUtils.load_and_decrypt_yaml(secure_file.read())
            self.assertTrue(is_encrypted)
            self.assertEqual('19', yaml_dict['params']['CALC_RESULT_SECURE'])

    def test_run_file_ops_pipeline(self):
        exec_dir = "files_pipeline_exec_dir"
        pipeline_data = "pipeline_configs/files/pipeline_files.yaml"
        output = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_dir={exec_dir}"])
        self.assertEqual(output.returncode, 0)
        with open(f'{exec_dir}/pipeline_output/output_params.yaml', 'r', encoding='utf-8') as file:
            result = yaml.safe_load(file)
            self.assertTrue(result['params']['FILE_SIZE'].endswith("KiB"))
            self.assertTrue(re.match(r'^\d+\.?\d*s$', result['params']['DL_TIME']))
            self.assertTrue(re.match(r'^\d+\.?\d* KiB$', result['params']['FILE_SIZE']))

    def test_run_failure_into_retry_success(self):
        exec_dir = "/retry_pipeline_exec_dir"
        pipeline_data = "pipeline_configs/retry/pipeline_retry_1.yaml"
        output_direct = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_dir={exec_dir}"])
        self.assertEqual(output_direct.returncode, 1)

        retry_vars = "CALC_OPERATION=add"
        output_retry = self._run_and_log([*self.PDE_CLI, "retry",
                                    f"--retry_vars={retry_vars}",
                                    f"--pipeline_dir={exec_dir}"])
        self.assertEqual(output_retry.returncode, 0)
        with open(f'{exec_dir}/pipeline_output/output_params.yaml', 'r', encoding='utf-8') as file:
            result = yaml.safe_load(file)
            self.assertEqual('16',  result['params']['CALC_3'])

    def test_run_performance_pipeline(self):
        exec_dir = "performance_pipeline_exec_dir"
        pipeline_data = "pipeline_configs/perf/pipeline_performance.yaml"
        start_time = time.perf_counter()
        output = self._run_and_log([*self.PDE_CLI, "run",
                                    f"--pipeline_data={pipeline_data}",
                                    f"--pipeline_dir={exec_dir}"])
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        expected_time = 7

        self.assertEqual(output.returncode, 0)
        self.assertLess(execution_time, expected_time,
                        f"Execution took {execution_time:.2f} seconds, expected less than {expected_time} seconds")


if __name__ == '__main__':
    unittest.main()
