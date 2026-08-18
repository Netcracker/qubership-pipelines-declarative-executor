import io
import logging


class DeliveryLogHandler(logging.Handler):
    terminator = "\n"

    def __init__(self):
        super().__init__()
        self._buffer = io.BytesIO()

    def emit(self, record):
        try:
            message = self.format(record) + self.terminator
            self._buffer.write(message.encode("utf-8", errors="replace"))
        except Exception:
            self.handleError(record)

    def get_snapshot(self) -> bytes:
        return self._buffer.getvalue()
