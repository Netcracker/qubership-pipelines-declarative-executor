import os, sys, re, pytest, logging
from textwrap import dedent

from _pytest.config import Config


class ResultsCollector:
    def __init__(self):
        self.failed_tests = []
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'total': 0,
            'pass_rate': 0,
            'duration': '0s'
        }

    def get_summary(self):
        return {
            **self.test_results,
            "failed_tests": self.failed_tests,
        }

    @pytest.hookimpl(trylast=True)
    def pytest_configure(self, config: Config):
        tr = config.pluginmanager.getplugin("terminalreporter")
        if tr is not None:
            oldwrite = tr._tw.write
            def tee_write(s, **kwargs):
                oldwrite(s, **kwargs)
                if isinstance(s, str) and s != "\n":
                    self._parse_stats(s)
                    self._collect_failed_tests(s)
            tr._tw.write = tee_write

    def _parse_stats(self, line: str):
        if not line.startswith("========================"):
            return
        if 'in' in line:
            duration_part = line.split('in')[-1].strip()
            duration_match = re.search(r'([\d.]+s)', duration_part)
            if duration_match:
                self.test_results['duration'] = duration_match.group(1)
        if 'failed' in line:
            failed_match = re.search(r'(\d+)\s+failed', line)
            if failed_match:
                self.test_results['failed'] = int(failed_match.group(1))
        if 'passed' in line:
            passed_match = re.search(r'(\d+)\s+passed', line)
            if passed_match:
                self.test_results['passed'] = int(passed_match.group(1))
        if 'skipped' in line:
            skipped_match = re.search(r'(\d+)\s+skipped', line)
            if skipped_match:
                self.test_results['skipped'] = int(skipped_match.group(1))
        self.test_results['total'] = (self.test_results['passed'] + self.test_results['failed'])
        self.test_results['pass_rate'] = (self.test_results['passed'] / self.test_results['total'] * 100
                                          if self.test_results['total'] > 0 else 0)

    def _collect_failed_tests(self, line: str):
        if 'FAILED' in line and '::' in line:
            test_name = line.split('FAILED')[-1].strip()
            self.failed_tests.append(test_name)


def write_step_summary(text: str):
    print(text)
    with open(os.getenv('GITHUB_STEP_SUMMARY'), 'w') as summary_file:
        summary_file.write(text)


def report_execution_result(is_success: bool, error: Exception = None, stats: dict = None):
    failed_tests = stats['failed_tests']
    pass_rate = stats['pass_rate']

    if is_success:
        message = dedent(f"""
        ## 🧪 Test Suite Report ✅
        ### 🎉 All Tests Passed! 
        **{stats['passed']}** tests completed successfully in **{stats['duration']}**
        
        ### 📊 Test Summary
        | Metric | Value |
        |--------|-------|
        | ✅ Passed | {stats['passed']} |
        | 📊 Total | {stats['total']} |
        | 🎯 Pass Rate | {pass_rate:.1f}% |
        | ⏱️ Duration | {stats['duration']} |
        """)
    else:
        failed_tests_list = "\n".join([f"• `{test}`" for test in failed_tests]) if failed_tests else "• No specific test details available"
        message = dedent(f"""
        ## 🧪 Test Suite Report ❌
        ### 🚨 Test Failures Detected
        **{stats['failed']}** out of **{stats['total']}** tests failed ({pass_rate:.1f}% pass rate)

        ### 📈 Test Summary
        | Metric | Value |
        |--------|-------|
        | ✅ Passed | {stats['passed']} |
        | ❌ Failed | {stats['failed']} |
        | 📊 Total | {stats['total']} |
        | 🎯 Pass Rate | {pass_rate:.1f}% |
        | ⏱️ Duration | {stats['duration']} |

        ### 🛑 Failed Tests
        {failed_tests_list}

        ### 📜 Error Details
        ```
        {error or "Tests failed - check details above"}
        ```
        """)
    write_step_summary(message)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format=u'[%(asctime)s] [%(levelname)-s] [%(filename)s]: %(message)s')
    pytest_report_collector = ResultsCollector()
    try:
        res = pytest.main(args=["./unit_tests"], plugins=[pytest_report_collector])
        if res != 0:
            raise Exception("Tests failed, check execution logs for details!")
        report_execution_result(True, stats=pytest_report_collector.get_summary())
    except Exception as e:
        report_execution_result(False, e, stats=pytest_report_collector.get_summary())
        exit(1)
