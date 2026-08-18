import json
import logging

from aiohttp import BasicAuth

from pipelines_declarative_executor.model.delivery import (
    DeliveryConfig,
    DeliveryMode,
    DeliveryPayload,
    EndpointType,
    HttpEndpointConfig,
    RemoteEndpointConfig,
    S3EndpointConfig,
)
from pipelines_declarative_executor.utils.env_var_utils import EnvVar, EnvVarUtils

S3_REQUIRED_FIELDS = ("host", "access_key", "secret_key", "bucket_name", "object_name")


class DeliveryConfigLoader:
    _cache: list[DeliveryConfig] | None = None

    @staticmethod
    def load_deliveries() -> list[DeliveryConfig]:
        if DeliveryConfigLoader._cache is not None:
            return DeliveryConfigLoader._cache
        try:
            DeliveryConfigLoader._cache = DeliveryConfigLoader._parse_deliveries()
        except Exception as e:
            logging.error(f"Exception loading {EnvVar.REMOTE_DELIVERIES_NAME} env var: [{type(e)} - {str(e)}]")
            DeliveryConfigLoader._cache = []
        return DeliveryConfigLoader._cache

    @staticmethod
    def clear_cache():
        DeliveryConfigLoader._cache = None

    @staticmethod
    def has_log_delivery() -> bool:
        return any(delivery.payload == DeliveryPayload.LOG for delivery in DeliveryConfigLoader.load_deliveries())

    @staticmethod
    def _parse_deliveries() -> list[DeliveryConfig]:
        config_json = EnvVarUtils.load_config_from_file_or_from_value(EnvVar.REMOTE_DELIVERIES_NAME)
        if not config_json:
            return []
        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {EnvVar.REMOTE_DELIVERIES_NAME}: {e}") from e
        if not isinstance(config_data, list):
            raise ValueError(f"{EnvVar.REMOTE_DELIVERIES_NAME} must contain a JSON array")
        return [DeliveryConfigLoader._parse_delivery(item, index) for index, item in enumerate(config_data)]

    @staticmethod
    def _parse_delivery(delivery_item: dict, index: int) -> DeliveryConfig:
        path = f"delivery[{index}]"
        if not isinstance(delivery_item, dict):
            raise ValueError(f"{path} must be a JSON object")

        payload = DeliveryConfigLoader._require_field(delivery_item, "payload", DeliveryPayload.parse, path)
        mode = DeliveryConfigLoader._require_field(delivery_item, "mode", DeliveryMode.parse, path)

        interval_seconds = delivery_item.get("interval_seconds")
        if mode == DeliveryMode.PERIODIC:
            if interval_seconds is None:
                raise KeyError(f"{path} with mode 'periodic' requires 'interval_seconds'")
            interval_seconds = float(interval_seconds)
            if interval_seconds <= 0:
                raise ValueError(f"{path} 'interval_seconds' must be greater than 0")

        endpoints_raw = delivery_item.get("endpoints")
        if not isinstance(endpoints_raw, list) or not endpoints_raw:
            raise ValueError(f"{path} requires a non-empty 'endpoints' array")

        endpoints = [
            DeliveryConfigLoader._parse_endpoint(endpoint_item, index, endpoint_index)
            for endpoint_index, endpoint_item in enumerate(endpoints_raw)
        ]
        return DeliveryConfig(payload=payload, mode=mode, interval_seconds=interval_seconds, endpoints=endpoints)

    @staticmethod
    def _parse_endpoint(endpoint_item: dict, delivery_index: int, endpoint_index: int) -> RemoteEndpointConfig:
        path = f"delivery[{delivery_index}].endpoints[{endpoint_index}]"
        if not isinstance(endpoint_item, dict):
            raise ValueError(f"{path} must be a JSON object")

        if "use_compression" not in endpoint_item:
            raise KeyError(f"{path} is missing required 'use_compression'")

        endpoint_type = DeliveryConfigLoader._require_field(endpoint_item, "type", EndpointType.parse, path)
        use_compression = endpoint_item["use_compression"]

        if endpoint_type == EndpointType.HTTP:
            endpoint = endpoint_item.get("endpoint")
            if not endpoint:
                raise KeyError(f"{path} is missing 'endpoint'")
            return HttpEndpointConfig(
                endpoint=endpoint,
                auth=DeliveryConfigLoader._get_basic_auth(endpoint_item),
                headers=DeliveryConfigLoader._get_headers(endpoint_item),
                use_compression=use_compression,
            )
        else:
            missing = [field for field in S3_REQUIRED_FIELDS if not endpoint_item.get(field)]
            if missing:
                raise KeyError(f"{path} is missing: {', '.join(missing)}")
            return S3EndpointConfig(
                **{field: endpoint_item[field] for field in S3_REQUIRED_FIELDS},
                use_compression=use_compression,
            )

    @staticmethod
    def _require_field(item: dict, field: str, parser, path: str):
        value = item.get(field)
        if not value:
            raise KeyError(f"{path} is missing required field '{field}'")
        try:
            return parser(value)
        except ValueError as e:
            raise ValueError(f"{path} has invalid {field}: {e}") from e

    @staticmethod
    def _get_basic_auth(config_item: dict) -> BasicAuth | None:
        if auth_data := config_item.get("auth"):
            username = EnvVarUtils.get_value_or_from_env(auth_data, "username")
            password = EnvVarUtils.get_value_or_from_env(auth_data, "password")
            if username and password:
                return BasicAuth(login=username, password=password)
        return None

    @staticmethod
    def _get_headers(config_item: dict) -> dict:
        token = EnvVarUtils.get_value_or_from_env(config_item, "token")
        headers = dict(config_item.get("headers") or {})
        for header_name, header_template in headers.items():
            headers[header_name] = header_template.format(token=token)
        return headers
