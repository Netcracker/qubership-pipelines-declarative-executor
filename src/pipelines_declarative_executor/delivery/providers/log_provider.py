from pipelines_declarative_executor.utils.logging_utils import LoggingUtils


class LogProvider:
    @staticmethod
    def build_payload() -> bytes | None:
        handler = LoggingUtils.get_delivery_log_handler()
        if not handler:
            return None
        snapshot = handler.get_snapshot()
        return snapshot if snapshot else b""
