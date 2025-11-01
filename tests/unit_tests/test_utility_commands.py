import os, logging, unittest, uuid
from pathlib import Path

from common import ExecutorTestCase


class TestUtilityCommands(ExecutorTestCase):

    PDE_CLI = ["python", "-m", "pipelines_declarative_executor"]

    def setUp(self):
        logging.info(os.getcwd())

    def test_create_archive_and_unarchive(self):
        archived_dir = "./test_archived_dir"
        archive_path = "./TARGET.zip"
        unarchive_path = "./test_unarchive_dir"
        test_file = "test.txt"

        Path(archived_dir).mkdir(parents=True, exist_ok=True)
        test_file_path = Path(archived_dir).joinpath(test_file)
        test_content = str(uuid.uuid4())
        with open(test_file_path, 'w') as fs:
            fs.write(test_content)

        archive_cmd_output = self._run_and_log([*self.PDE_CLI, "archive", f"--pipeline_dir={archived_dir}",
                                    f"--target_path={archive_path}"])
        self.assertEqual(archive_cmd_output.returncode, 0)
        self.assertTrue(os.path.exists(archive_path))

        unarchive_cmd_output = self._run_and_log([*self.PDE_CLI, "unarchive", f"--archive_path={archive_path}",
                                    f"--target_path={unarchive_path}"])
        self.assertEqual(unarchive_cmd_output.returncode, 0)
        self.assertTrue(os.path.exists(unarchive_path))
        with open(Path(unarchive_path).joinpath(archived_dir).joinpath(test_file), 'r', encoding='utf-8') as f:
            self.assertEqual(test_content, f.read().strip())

    def test_archive_fails_on_missing_path(self):
        output = self._run_and_log([*self.PDE_CLI, "archive", "--pipeline_dir=/random_non_existent_dir",
                                    "--target_path=TARGET.zip", "--fail_on_missing=true"])
        self.assertEqual(output.returncode, 1)
        self.assertTrue("Trying to archive non-existent path" in output.stdout + output.stderr)


if __name__ == '__main__':
    unittest.main()
