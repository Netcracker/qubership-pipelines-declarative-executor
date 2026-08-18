import asyncio
import json
import gzip
import os
import signal
import subprocess
import threading
import time
from base64 import b64decode
from aiohttp import web

from common import ExecutorTestCase
with_exec_dir = ExecutorTestCase.with_exec_dir

TEST_USER = "test_user"
TEST_PASS = "test_pass"
TEST_TOKEN = "test_token"


class _DeliveryTestServer:
    def __init__(self):
        self.received_reports = []
        self.received_statuses = []
        self.received_logs = []
        self.port = None
        self._thread = None
        self._started = threading.Event()
        self._loop = None
        self._runner = None

    def start(self):
        self.received_reports.clear()
        self.received_statuses.clear()
        self.received_logs.clear()
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
        app.router.add_post("/report", self._handle_report)
        app.router.add_post("/status", self._handle_status)
        app.router.add_post("/log", self._handle_log)
        self._runner = web.AppRunner(app, auto_decompress=False)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "localhost", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        self._started.set()

    async def _authorize(self, request):
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
        return None

    async def _read_body(self, request):
        body = await request.read()
        if request.headers.get("Content-Encoding", "") == "gzip":
            body = gzip.decompress(body)
        return body

    async def _handle_report(self, request):
        if auth_error := await self._authorize(request):
            return auth_error
        body = await self._read_body(request)
        report = json.loads(body.decode("utf-8"))
        self.received_reports.append(report)
        return web.Response(text="OK", status=200)

    async def _handle_status(self, request):
        if auth_error := await self._authorize(request):
            return auth_error
        body = await self._read_body(request)
        status_payload = json.loads(body.decode("utf-8"))
        self.received_statuses.append(status_payload)
        return web.Response(text="OK", status=200)

    async def _handle_log(self, request):
        if auth_error := await self._authorize(request):
            return auth_error
        body = await self._read_body(request)
        self.received_logs.append(body.decode("utf-8"))
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


def _report_delivery(endpoint: str, mode: str, interval_seconds: int | None = None, use_token: bool = False) -> dict:
    endpoint_config = {
        "type": "http",
        "endpoint": endpoint,
        "headers": {"Content-Type": "application/json"},
        "use_compression": False,
    }
    if use_token:
        endpoint_config["token_value"] = TEST_TOKEN
        endpoint_config["headers"]["Authorization"] = "Bearer {token}"
    else:
        endpoint_config["auth"] = {
            "username_value": TEST_USER,
            "password_value": TEST_PASS,
        }

    delivery = {
        "payload": "report",
        "mode": mode,
        "endpoints": [endpoint_config],
    }
    if interval_seconds is not None:
        delivery["interval_seconds"] = interval_seconds
    return delivery


class TestRemoteDeliveries(ExecutorTestCase):

    @with_exec_dir
    def test_report_delivery_on_completion(self):
        server = _DeliveryTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"] = json.dumps([
                _report_delivery(endpoint, mode="on_completion"),
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
    def test_report_delivery_periodic(self):
        server = _DeliveryTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"] = json.dumps([
                _report_delivery(endpoint, mode="periodic", interval_seconds=1, use_token=True),
            ])

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
            self.assertTrue(
                any(report.get("status") == "IN_PROGRESS" for report in server.received_reports[:-1]),
                "expected at least one in-progress periodic report before the final flush",
            )

            last_report = server.received_reports[-1]
            self.assertEqual(last_report["status"], "SUCCESS")
            stages = last_report["stages"]
            for stage in stages:
                self.assertEqual(stage["status"], "SUCCESS")
        finally:
            server.stop()

    @with_exec_dir
    def test_report_delivery_on_cancellation(self):
        server = _DeliveryTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/report"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"] = json.dumps([
                _report_delivery(endpoint, mode="on_completion"),
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

    @with_exec_dir
    def test_status_delivery_periodic(self):
        server = _DeliveryTestServer()
        server.start()
        try:
            endpoint = f"http://localhost:{server.port}/status"
            env = os.environ.copy()
            env["PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES"] = json.dumps([{
                "payload": "status",
                "mode": "periodic",
                "interval_seconds": 1,
                "endpoints": [{
                    "type": "http",
                    "endpoint": endpoint,
                    "token_value": TEST_TOKEN,
                    "headers": {
                        "Authorization": "Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    "use_compression": False,
                }],
            }])

            pipeline_data = "pipeline_configs/report/pipeline_report_upload_test.yaml"
            pipeline_vars = "SLEEP_TIME=3"
            output = self._run_and_log(
                [*self.PDE_CLI, "run", f"--pipeline_data={pipeline_data}",
                 f"--pipeline_vars={pipeline_vars}", f"--pipeline_dir={self.exec_dir}"],
                env=env,
            )
            self.assertEqual(output.returncode, 0)
            time.sleep(0.5)

            self.assertGreaterEqual(len(server.received_statuses), 1)
            status_payload = server.received_statuses[-1]
            self.assertEqual(status_payload["status"], "SUCCESS")
            self.assertIn("progress", status_payload)
            self.assertNotIn("config", status_payload)
            self.assertNotIn("stages", status_payload)
        finally:
            server.stop()
