import asyncio, json, gzip, os, signal, subprocess, threading, time
from base64 import b64decode
from aiohttp import web

from common import ExecutorTestCase
with_exec_dir = ExecutorTestCase.with_exec_dir

TEST_USER = "test_user"
TEST_PASS = "test_pass"
TEST_TOKEN = "test_token"


class _ReportTestServer:
    def __init__(self):
        self.received_reports = []
        self.port = None
        self._thread = None
        self._started = threading.Event()
        self._loop = None
        self._runner = None

    def start(self):
        self.received_reports.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._started.wait(timeout=10):
            raise RuntimeError("Server did not start within 10 seconds")

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())
        self._loop.run_forever()

    async def _serve(self):
        app = web.Application()
        app.router.add_post("/report", self._handle_post)
        self._runner = web.AppRunner(app, auto_decompress=False)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "localhost", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        self._started.set()

    async def _handle_post(self, request):
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Basic "):
            try:
                encoded = auth_header.split(" ", 1)[1]
                decoded = b64decode(encoded).decode("utf-8")
                username, password = decoded.split(":", 1)
                if username != TEST_USER or password != TEST_PASS:
                    return web.Response(text="Invalid credentials", status=403)
            except Exception:
                return web.Response(text="Invalid auth header", status=400)

        elif auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            if token != TEST_TOKEN:
                return web.Response(text="Invalid credentials", status=403)

        else:
            return web.Response(text="Authentication required", status=401)

        body = await request.read()
        if request.headers.get("Content-Encoding", "") == "gzip":
            body = gzip.decompress(body)

        report = json.loads(body.decode("utf-8"))
        self.received_reports.append(report)
        return web.Response(text="OK", status=200)

    def stop(self):
        if self._loop is None:
            return
        if self._runner:
            self._loop.call_soon_threadsafe(self._do_stop)
        else:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def _do_stop(self):
        asyncio.create_task(self._cleanup_and_stop())

    async def _cleanup_and_stop(self):
        await self._runner.cleanup()
        self._loop.stop()


class TestReportUploader(ExecutorTestCase):

    @with_exec_dir
    def test_report_upload_on_completion(self):
        server = _ReportTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS"] = json.dumps([
                {
                    "type": "http",
                    "endpoint": endpoint,
                    "auth": {
                        "username_value": TEST_USER,
                        "password_value": TEST_PASS,
                    },
                },
            ])

            pipeline_data = "pipeline_configs/report/pipeline_report_upload_test.yaml"
            pipeline_vars = "SLEEP_TIME=0"
            output = self._run_and_log(
                [*self.PDE_CLI, "run", f"--pipeline_data={pipeline_data}",
                 f"--pipeline_vars={pipeline_vars}", f"--pipeline_dir={self.exec_dir}"],
                env=env,
            )
            self.assertEqual(output.returncode, 0)

            time.sleep(0.5)

            self.assertEqual(len(server.received_reports), 1)
            report = server.received_reports[0]

            self.assertEqual(report["kind"], "AtlasPipelineReport")
            self.assertEqual(report["apiVersion"], "v2")
            self.assertEqual(report["name"], "Pipeline Report Upload Test")
            self.assertEqual(report["status"], "SUCCESS")
            self.assertIsNotNone(report["id"])
            self.assertIsNotNone(report["startedAt"])
            self.assertIsNotNone(report["finishedAt"])

            self.assertIn("performance", report)
            self.assertIn("peakMemory", report["performance"])
            self.assertIn("peakCpu", report["performance"])

            stages = report["stages"]
            self.assertEqual(len(stages), 2)
            for stage in stages:
                self.assertEqual(stage["status"], "SUCCESS")
        finally:
            server.stop()

    @with_exec_dir
    def test_report_upload_periodic(self):
        server = _ReportTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS"] = json.dumps([
                {
                    "type": "http",
                    "endpoint": endpoint,
                    "token_value": TEST_TOKEN,
                    "headers": {
                        "Authorization": "Bearer {token}",
                    },
                },
            ])
            env["PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_MODE"] = "PERIODIC"
            env["PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_INTERVAL"] = "1"

            pipeline_data = "pipeline_configs/report/pipeline_report_upload_test.yaml"
            pipeline_vars = "SLEEP_TIME=3"
            output = self._run_and_log(
                [*self.PDE_CLI, "run", f"--pipeline_data={pipeline_data}",
                 f"--pipeline_vars={pipeline_vars}", f"--pipeline_dir={self.exec_dir}"],
                env=env,
            )
            self.assertEqual(output.returncode, 0)

            time.sleep(0.5)

            self.assertGreaterEqual(len(server.received_reports), 2)

            last_report = server.received_reports[-1]
            self.assertEqual(last_report["status"], "SUCCESS")
            stages = last_report["stages"]
            for stage in stages:
                self.assertEqual(stage["status"], "SUCCESS")
        finally:
            server.stop()

    @with_exec_dir
    def test_report_upload_on_cancellation(self):
        server = _ReportTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS"] = json.dumps([
                {
                    "type": "http",
                    "endpoint": endpoint,
                    "auth": {
                        "username_value": TEST_USER,
                        "password_value": TEST_PASS,
                    },
                },
            ])

            pipeline_data = "pipeline_configs/report/pipeline_report_upload_test.yaml"
            pipeline_vars = "SLEEP_TIME=30"
            command = [*self.PDE_CLI, "run", f"--pipeline_data={pipeline_data}",
                       f"--pipeline_vars={pipeline_vars}", f"--pipeline_dir={self.exec_dir}"]

            process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            time.sleep(2)
            process.send_signal(signal.SIGINT)

            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 1)
            time.sleep(0.5)

            self.assertEqual(len(server.received_reports), 1)
            report = server.received_reports[0]
            self.assertEqual(report["status"], "CANCELLED")

            stages = report["stages"]
            self.assertEqual(len(stages), 2)
            self.assertEqual(stages[0]["status"], "CANCELLED")
            self.assertEqual(stages[1]["status"], "NOT_STARTED")
        finally:
            server.stop()
