import asyncio
import unittest
from types import SimpleNamespace

import aiohttp

from pipelines_declarative_executor.delivery.sender import DeliverySender, _HttpTarget
from pipelines_declarative_executor.model.delivery import DeliveryPayload

ENDPOINT = "http://pde-operator.test/runs/1/deliveries/status"


class _StubPost:
    def __init__(self, connection_error: Exception | None = None, status_error: Exception | None = None):
        self._connection_error = connection_error
        self._status_error = status_error

    async def __aenter__(self):
        if self._connection_error is not None:
            raise self._connection_error
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error


class _StubSession:
    def __init__(self, connection_errors: list[Exception] | None = None, status_error: Exception | None = None):
        self._connection_errors = list(connection_errors or [])
        self._status_error = status_error
        self.attempts = 0

    def post(self, endpoint, data=None):
        self.attempts += 1
        connection_error = self._connection_errors.pop(0) if self._connection_errors else None
        return _StubPost(connection_error=connection_error, status_error=self._status_error)


class TestHttpDeliveryRetry(unittest.TestCase):

    @staticmethod
    def _target(session: _StubSession) -> _HttpTarget:
        return _HttpTarget(session=session, endpoint=ENDPOINT, use_compression=False, payload=DeliveryPayload.STATUS)

    def _upload(self, session: _StubSession):
        asyncio.run(DeliverySender._upload_via_http(self._target(session), b"{}"))

    def test_retries_once_after_connection_error(self):
        session = _StubSession(connection_errors=[aiohttp.ClientOSError(104, "Connection reset by peer")])
        with self.assertNoLogs(level="WARNING"):
            self._upload(session)
        self.assertEqual(session.attempts, 2)

    def test_warns_when_connection_error_persists(self):
        session = _StubSession(connection_errors=[
            aiohttp.ServerDisconnectedError(),
            aiohttp.ServerDisconnectedError(),
        ])
        with self.assertLogs(level="WARNING") as logs:
            self._upload(session)
        self.assertEqual(session.attempts, 2)
        self.assertIn("Exception during HTTP delivery", "\n".join(logs.output))

    def test_does_not_retry_http_error_status(self):
        request_info = SimpleNamespace(real_url=ENDPOINT)
        session = _StubSession(status_error=aiohttp.ClientResponseError(request_info, (), status=500))
        with self.assertLogs(level="WARNING"):
            self._upload(session)
        self.assertEqual(session.attempts, 1)
