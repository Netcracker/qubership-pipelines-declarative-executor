import asyncio, aiohttp, logging, json, io

from aiohttp import BasicAuth
from miniopy_async import Minio

from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.report import RemoteEndpointConfig, HttpEndpointConfig, S3EndpointConfig, ReportUploadMode
from pipelines_declarative_executor.model.stage import ExecutionStatus
from pipelines_declarative_executor.report.report_collector import ReportCollector
from pipelines_declarative_executor.utils.env_var_utils import EnvVar, EnvVarUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


class ReportUploader:
    def __init__(self, execution: PipelineExecution, configs: list[RemoteEndpointConfig], **kwargs):
        self.execution = execution
        self.http_sessions = []
        self.s3_clients = []
        for config in configs:
            if isinstance(config, HttpEndpointConfig):
                self.http_sessions.append({
                    "session": aiohttp.ClientSession(auth=config.auth, headers=config.headers),
                    "endpoint": config.endpoint,
                })
            elif isinstance(config, S3EndpointConfig):
                self.s3_clients.append({
                    "client": Minio(
                        endpoint=config.host,
                        access_key=config.access_key,
                        secret_key=config.secret_key,
                        secure=False
                    ),
                    "bucket_name": config.bucket_name,
                    "object_name": config.object_name,
                })
            else:
                logging.error(f"Unknown report RemoteEndpointConfig type: {type(config)}")

    async def __aenter__(self):
        await self._upload_handler()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        cleanup_tasks = []
        for session_info in self.http_sessions:
            if not session_info["session"].closed:
                cleanup_tasks.append(session_info["session"].close())
        for s3_client in self.s3_clients:
            cleanup_tasks.append(s3_client["client"].close_session())
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    async def _upload_handler(self):
        if not self.http_sessions and not self.s3_clients:
            logging.warning("No remote endpoints were configured for ReportUploader, no reports will be uploaded!")
            return
        if EnvVar.REPORT_SEND_MODE == ReportUploadMode.PERIODIC:
            while self.execution.status not in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                await self._send_report()
                await asyncio.sleep(EnvVar.REPORT_SEND_INTERVAL)
            logging.debug("Sending FINAL execution report...")
            await self._send_report()
        elif EnvVar.REPORT_SEND_MODE == ReportUploadMode.ON_COMPLETION:
            while self.execution.status not in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                await asyncio.sleep(EnvVar.REPORT_STATUS_POLL_INTERVAL)
            logging.debug("Sending ON_COMPLETION execution report...")
            await self._send_report()

    async def _send_report(self):
        try:
            report = self._get_report()
            upload_tasks = []
            for session_data in self.http_sessions:
                upload_tasks.append(self._upload_via_http(session_data, report))
            for s3_data in self.s3_clients:
                upload_tasks.append(self._upload_via_s3(s3_data, report))
            await asyncio.gather(*upload_tasks, return_exceptions=True)
        except Exception as e:
            logging.error(f"Exception during sending report: [{type(e)} - {str(e)}]")

    def _get_report(self) -> str:
        if self.execution.state_dir and self.execution.state_dir.exists():
            report = ReportCollector.prepare_ui_view(self.execution)
            return json.dumps(report, default=StringUtils.json_encode)
        raise Exception("Report not found!")

    @staticmethod
    async def _upload_via_http(session_data: dict, report: str):
        try:
            logging.debug(f"Uploading execution report via HTTP to {session_data.get('endpoint')}")
            async with session_data.get("session").post(session_data.get("endpoint"), json=json.loads(report)) as response:
                response.raise_for_status()
                logging.debug(f"Upload via HTTP to {session_data.get('endpoint')} finished")
        except Exception as e:
            logging.error(f"Exception during uploading report via HTTP: [{type(e)} - {str(e)}]")

    @staticmethod
    async def _upload_via_s3(s3_data: dict, report: str):
        try:
            logging.debug(f"Uploading execution report via S3 to bucket {s3_data.get('bucket_name')}")
            report_bytes = report.encode('utf-8')
            data_stream = io.BytesIO(report_bytes)
            await s3_data.get("client").put_object(
                bucket_name=s3_data.get("bucket_name"),
                object_name=s3_data.get("object_name"),
                data=data_stream,
                length=len(report_bytes),
                content_type='application/json'
            )
            logging.debug(f"Upload via S3 to bucket '{s3_data.get('bucket_name')}' finished")
        except Exception as e:
            logging.error(f"Exception during uploading report via S3: [{type(e)} - {str(e)}]")

    @staticmethod
    def load_endpoint_configs() -> list[RemoteEndpointConfig]:
        configs = []
        try:
            configs = ReportUploader._get_endpoint_configs()
        except Exception as e:
            logging.error(f"Exception loading {EnvVar.REPORT_REMOTE_ENDPOINTS_NAME} Env var: [{type(e)} - {str(e)}]")
        return configs

    @staticmethod
    def _get_endpoint_configs() -> list[RemoteEndpointConfig]:
        """
        Loads endpoint configurations from the EnvVar.REPORT_REMOTE_ENDPOINTS_NAME environment variable.
        """
        endpoint_configs = []
        config_json = EnvVarUtils.load_config_from_file_or_from_value(EnvVar.REPORT_REMOTE_ENDPOINTS_NAME)
        if not config_json:
            return endpoint_configs
        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {EnvVar.REPORT_REMOTE_ENDPOINTS_NAME}: {e}")

        if not isinstance(config_data, list):
            raise ValueError(f"{EnvVar.REPORT_REMOTE_ENDPOINTS_NAME} must contain a JSON array")

        for config_item in config_data:
            if not isinstance(config_item, dict):
                raise ValueError("Each endpoint configuration must be a JSON object")

            config_type = config_item.get("type")
            if not config_type:
                raise KeyError("Endpoint configuration missing 'type' field")

            if config_type == "http":
                endpoint_config = HttpEndpointConfig(
                    endpoint=config_item.get("endpoint"),
                    auth=ReportUploader._get_basic_auth(config_item),
                    headers=ReportUploader._get_headers(config_item)
                )

            elif config_type == "s3":
                endpoint_config = S3EndpointConfig(
                    host=config_item.get("host"),
                    access_key=config_item.get("access_key"),
                    secret_key=config_item.get("secret_key"),
                    bucket_name=config_item.get("bucket_name"),
                    object_name=config_item.get("object_name")
                )

            else:
                raise ValueError(f"Unknown endpoint type: {config_type}")

            endpoint_configs.append(endpoint_config)

        return endpoint_configs

    @staticmethod
    def _get_basic_auth(config_item: dict) -> BasicAuth | None:
        if auth_data := config_item.get("auth"):
            username = EnvVarUtils.get_value_or_from_env(auth_data, 'username')
            password = EnvVarUtils.get_value_or_from_env(auth_data, 'password')
            if username and password:
                return BasicAuth(login=username, password=password)
        return None

    @staticmethod
    def _get_headers(config_item: dict) -> dict:
        token = EnvVarUtils.get_value_or_from_env(config_item, 'token')
        headers = config_item.get("headers", {})
        for header_name, header_template in headers.items():
            header_value = header_template.format(token=token)
            headers[header_name] = header_value
        return headers
