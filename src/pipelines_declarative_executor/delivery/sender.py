import asyncio
import gzip
import io
import logging
from dataclasses import dataclass, field

import aiohttp
from miniopy_async import Minio

from pipelines_declarative_executor.model.delivery import (
    DeliveryConfig,
    DeliveryPayload,
    HttpEndpointConfig,
    S3EndpointConfig,
)


@dataclass
class _HttpTarget:
    session: aiohttp.ClientSession
    endpoint: str
    use_compression: bool
    payload: DeliveryPayload


@dataclass
class _S3Target:
    client: Minio
    bucket_name: str
    object_name: str
    use_compression: bool
    payload: DeliveryPayload


@dataclass
class _DeliveryTargets:
    http: list[_HttpTarget] = field(default_factory=list)
    s3: list[_S3Target] = field(default_factory=list)


class DeliverySender:
    CONTENT_TYPES = {
        DeliveryPayload.STATUS: "application/json",
        DeliveryPayload.REPORT: "application/json",
        DeliveryPayload.LOG: "text/plain",
    }

    def __init__(self, deliveries: list[DeliveryConfig] | None = None):
        self._targets: dict[int, _DeliveryTargets] = {}
        for delivery in deliveries or []:
            self._targets[id(delivery)] = self._build_targets(delivery)

    async def send(self, delivery: DeliveryConfig, body: bytes):
        if not body and delivery.payload != DeliveryPayload.LOG:
            return

        targets = self._targets.get(id(delivery))
        if not targets:
            return

        upload_tasks = [
            self._upload_via_http(http_target, body)
            for http_target in targets.http
        ] + [
            self._upload_via_s3(s3_target, body)
            for s3_target in targets.s3
        ]
        if upload_tasks:
            await asyncio.gather(*upload_tasks, return_exceptions=True)

    async def close(self):
        cleanup_tasks = []
        for targets in self._targets.values():
            for http_target in targets.http:
                if not http_target.session.closed:
                    cleanup_tasks.append(http_target.session.close())
            for s3_target in targets.s3:
                cleanup_tasks.append(s3_target.client.close_session())
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    def _build_targets(self, delivery: DeliveryConfig) -> _DeliveryTargets:
        targets = _DeliveryTargets()
        for endpoint in delivery.endpoints:
            if isinstance(endpoint, HttpEndpointConfig):
                targets.http.append(self._build_http_target(delivery.payload, endpoint))
            elif isinstance(endpoint, S3EndpointConfig):
                targets.s3.append(self._build_s3_target(delivery.payload, endpoint))
            else:
                logging.error(f"Unknown remote endpoint type for {delivery.payload} delivery: {type(endpoint)}")
        return targets

    def _build_http_target(self, payload: DeliveryPayload, endpoint: HttpEndpointConfig) -> _HttpTarget:
        headers = dict(endpoint.headers or {})
        if endpoint.use_compression:
            headers["Content-Encoding"] = "gzip"
        if "Content-Type" not in headers:
            headers["Content-Type"] = self.CONTENT_TYPES[payload]
        return _HttpTarget(
            session=aiohttp.ClientSession(auth=endpoint.auth, headers=headers),
            endpoint=endpoint.endpoint,
            use_compression=endpoint.use_compression,
            payload=payload,
        )

    def _build_s3_target(self, payload: DeliveryPayload, endpoint: S3EndpointConfig) -> _S3Target:
        return _S3Target(
            client=Minio(
                endpoint=endpoint.host,
                access_key=endpoint.access_key,
                secret_key=endpoint.secret_key,
                secure=False,
            ),
            bucket_name=endpoint.bucket_name,
            object_name=endpoint.object_name,
            use_compression=endpoint.use_compression,
            payload=payload,
        )

    @staticmethod
    def _encode_body(body: bytes, use_compression: bool) -> bytes:
        return gzip.compress(body) if use_compression else body

    @staticmethod
    async def _upload_via_http(http_target: _HttpTarget, body: bytes):
        try:
            logging.debug(f"Uploading {http_target.payload} delivery via HTTP to {http_target.endpoint}")
            request_body = DeliverySender._encode_body(body, http_target.use_compression)
            async with http_target.session.post(http_target.endpoint, data=request_body) as response:
                response.raise_for_status()
                logging.debug(f"Upload via HTTP to {http_target.endpoint} finished")
        except Exception as e:
            logging.warning(f"Exception during HTTP delivery to {http_target.endpoint}: [{type(e)} - {str(e)}]")

    @staticmethod
    async def _upload_via_s3(s3_target: _S3Target, body: bytes):
        try:
            logging.debug(f"Uploading {s3_target.payload} delivery via S3 to bucket {s3_target.bucket_name}")
            request_body = DeliverySender._encode_body(body, s3_target.use_compression)
            metadata = {"Content-Encoding": "gzip"} if s3_target.use_compression else None
            await s3_target.client.put_object(
                bucket_name=s3_target.bucket_name,
                object_name=s3_target.object_name,
                data=io.BytesIO(request_body),
                length=len(request_body),
                content_type=DeliverySender.CONTENT_TYPES[s3_target.payload],
                metadata=metadata,
            )
            logging.debug(f"Upload via S3 to bucket '{s3_target.bucket_name}' finished")
        except Exception as e:
            logging.warning(f"Exception during S3 delivery: [{type(e)} - {str(e)}]")
