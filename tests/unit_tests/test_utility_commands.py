import os, unittest, uuid
from pathlib import Path

from common import ExecutorTestCase


class TestUtilityCommands(ExecutorTestCase):

    def test_help_option(self):
        output = self._run_and_log([*self.PDE_CLI, "--help"])
        self.assertTrue("Commands:" in output.stdout + output.stderr)

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


class TestStringUtils(unittest.TestCase):

    def setUp(self):
        from pipelines_declarative_executor.utils.string_utils import StringUtils
        self.duration_str_to_seconds = StringUtils.duration_str_to_seconds

    def test_duration_str_to_seconds(self):
        # plain seconds
        self.assertEqual(self.duration_str_to_seconds("0s"), 0)
        self.assertEqual(self.duration_str_to_seconds("5s"), 5)
        self.assertEqual(self.duration_str_to_seconds("0.5s"), 0.5)
        self.assertEqual(self.duration_str_to_seconds("10.75s"), 10.75)

        # default unit is seconds when omitted
        self.assertEqual(self.duration_str_to_seconds("5"), 5)
        self.assertEqual(self.duration_str_to_seconds("0"), 0)

        # minutes
        self.assertEqual(self.duration_str_to_seconds("1m"), 60)
        self.assertEqual(self.duration_str_to_seconds("2m"), 120)
        self.assertEqual(self.duration_str_to_seconds("0.5m"), 30)

        # hours
        self.assertEqual(self.duration_str_to_seconds("1h"), 3600)
        self.assertEqual(self.duration_str_to_seconds("2h"), 7200)
        self.assertEqual(self.duration_str_to_seconds("0.5h"), 1800)

        # whitespace tolerance
        self.assertEqual(self.duration_str_to_seconds("  5s  "), 5)
        self.assertEqual(self.duration_str_to_seconds(" 1 m "), 60)

        # large values
        self.assertEqual(self.duration_str_to_seconds("3600s"), 3600)
        self.assertEqual(self.duration_str_to_seconds("120m"), 7200)
        self.assertEqual(self.duration_str_to_seconds("24h"), 86400)

        # invalid cases
        for invalid in ["", "abc", "5x", "-1s", "1.2.3s"]:
            with self.assertRaises(ValueError, msg=f"Expected ValueError for '{invalid}'"):
                self.duration_str_to_seconds(invalid)


if __name__ == '__main__':
    unittest.main()
