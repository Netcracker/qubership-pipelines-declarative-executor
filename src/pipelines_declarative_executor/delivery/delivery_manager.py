import asyncio

from pipelines_declarative_executor.delivery.config_loader import DeliveryConfigLoader
from pipelines_declarative_executor.delivery.providers.log_provider import LogProvider
from pipelines_declarative_executor.delivery.providers.report_provider import ReportProvider
from pipelines_declarative_executor.delivery.providers.status_provider import StatusProvider
from pipelines_declarative_executor.delivery.sender import DeliverySender
from pipelines_declarative_executor.model.delivery import DeliveryConfig, DeliveryMode, DeliveryPayload
from pipelines_declarative_executor.model.pipeline import PipelineExecution


class DeliveryManager:
    def __init__(self, execution: PipelineExecution, deliveries: list[DeliveryConfig] | None = None):
        self.execution = execution
        self.deliveries = deliveries if deliveries is not None else DeliveryConfigLoader.load_deliveries()
        self._sender = DeliverySender(self.deliveries)
        self._periodic_tasks: list[asyncio.Task] = []

    async def __aenter__(self):
        if not self.deliveries:
            return self

        for delivery in self.deliveries:
            if delivery.mode == DeliveryMode.PERIODIC:
                self._periodic_tasks.append(asyncio.create_task(self._periodic_send(delivery)))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._periodic_tasks:
            for task in self._periodic_tasks:
                task.cancel()
            await asyncio.gather(*self._periodic_tasks, return_exceptions=True)

        await self._flush_all()
        await self._sender.close()

    async def _flush_all(self):
        if not self.deliveries:
            return
        await asyncio.gather(*[self._send_delivery(delivery) for delivery in self.deliveries], return_exceptions=True)

    async def _periodic_send(self, delivery: DeliveryConfig):
        try:
            while True:
                await self._send_delivery(delivery)
                await asyncio.sleep(delivery.interval_seconds)
        except asyncio.CancelledError:
            pass

    async def _send_delivery(self, delivery: DeliveryConfig):
        body = self._build_payload(delivery.payload)
        if body is None:
            return
        await self._sender.send(delivery, body)

    def _build_payload(self, payload: DeliveryPayload) -> bytes | None:
        if payload == DeliveryPayload.STATUS:
            return StatusProvider.build_payload(self.execution)
        if payload == DeliveryPayload.REPORT:
            return ReportProvider.build_payload(self.execution)
        if payload == DeliveryPayload.LOG:
            return LogProvider.build_payload()
        return None
