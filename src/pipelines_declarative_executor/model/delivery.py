from dataclasses import dataclass
from enum import StrEnum

from aiohttp import BasicAuth


class DeliveryPayload(StrEnum):
    STATUS = "status"
    REPORT = "report"
    LOG = "log"

    @classmethod
    def parse(cls, value: str) -> "DeliveryPayload":
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Unknown delivery payload: {value!r}") from e


class DeliveryMode(StrEnum):
    PERIODIC = "periodic"
    ON_COMPLETION = "on_completion"

    @classmethod
    def parse(cls, value: str) -> "DeliveryMode":
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Unknown delivery mode: {value!r}") from e


class EndpointType(StrEnum):
    HTTP = "http"
    S3 = "s3"

    @classmethod
    def parse(cls, value: str) -> "EndpointType":
        try:
            return cls(value.lower())
        except ValueError as e:
            raise ValueError(f"Unknown endpoint type: {value!r}") from e


class RemoteEndpointConfig:
    pass


@dataclass
class HttpEndpointConfig(RemoteEndpointConfig):
    endpoint: str = None
    auth: BasicAuth = None
    headers: dict = None
    use_compression: bool = None


@dataclass
class S3EndpointConfig(RemoteEndpointConfig):
    host: str = None
    access_key: str = None
    secret_key: str = None
    bucket_name: str = None
    object_name: str = None
    use_compression: bool = None


@dataclass
class DeliveryConfig:
    payload: DeliveryPayload
    mode: DeliveryMode
    interval_seconds: float = None
    endpoints: list[RemoteEndpointConfig] = None
