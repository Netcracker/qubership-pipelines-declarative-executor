from dataclasses import dataclass
from enum import StrEnum
from aiohttp import BasicAuth


class RemoteEndpointConfig:
    pass


@dataclass
class HttpEndpointConfig(RemoteEndpointConfig):
    endpoint: str = None
    auth: BasicAuth = None
    headers: dict = None


@dataclass
class S3EndpointConfig(RemoteEndpointConfig):
    host: str = None
    access_key: str = None
    secret_key: str = None
    bucket_name: str = None
    object_name: str = None


class ReportUploadMode(StrEnum):
    PERIODIC = "PERIODIC"
    ON_COMPLETION = "ON_COMPLETION"
