import io
import logging


class DeliveryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self._buffer = io.BytesIO()

    def emit(self, record):
        try:
            self._buffer.write(self.format(record).encode("utf-8", errors="replace"))
            self._buffer.write(self.terminator.encode("utf-8"))
        except Exception:
            self.handleError(record)

    def get_snapshot(self) -> bytes:
        return self._buffer.getvalue()
