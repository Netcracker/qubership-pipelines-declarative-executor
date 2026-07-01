from __future__ import annotations

import logging, re


class ColorUtils:

    SUCCESS_COLOR = "GREEN"
    FAILURE_COLOR = "RED"
    WARNING_COLOR = "ORANGE"

    STATUS_COLORS = {
        'SUCCESS': SUCCESS_COLOR,
        'FAILED': FAILURE_COLOR,
    }

    COLOR_CODES = {
        'BLUE': '\033[38;5;67m',  # steel_blue
        'GREEN': '\033[38;5;79m',  # light_sea_green
        'ORANGE': '\033[38;5;172m',  # orange
        'RED': '\033[38;5;131m',  # indian_red
        'VIOLET': '\033[38;5;162m',  # medium_violet_red
        'RESET': '\033[0m',
    }
    ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*m')

    @staticmethod
    def with_color(message: str, color: str) -> str:
        if color in ColorUtils.COLOR_CODES:
            return f"{ColorUtils.COLOR_CODES[color]}{message}{ColorUtils.COLOR_CODES['RESET']}"
        else:
            return message

    @staticmethod
    def colorize_status(status) -> str:
        status = str(status)
        return ColorUtils.with_color(status, ColorUtils.STATUS_COLORS.get(status))

    @staticmethod
    def strip_ansi(text: str) -> str:
        if '\x1b' not in text:
            return text
        return ColorUtils.ANSI_PATTERN.sub('', text)


class ColoredFormatter(logging.Formatter):

    COLOR_CODES = {
        'DEBUG': ColorUtils.COLOR_CODES['BLUE'],
        'INFO': ColorUtils.COLOR_CODES['GREEN'],
        'WARNING': ColorUtils.COLOR_CODES['ORANGE'],
        'ERROR': ColorUtils.COLOR_CODES['RED'],
        'CRITICAL': ColorUtils.COLOR_CODES['VIOLET'],
        'RESET': ColorUtils.COLOR_CODES['RESET'],
    }

    def format(self, record):
        record = logging.makeLogRecord(record.__dict__)
        levelname = record.levelname
        if levelname in self.COLOR_CODES:
            record.levelname = f"{self.COLOR_CODES[levelname]}{levelname}{self.COLOR_CODES['RESET']}"
        return super().format(record)


class PlainFormatter(logging.Formatter):
    """Strips ANSI color/style codes from the fully-formatted line."""

    def format(self, record):
        return ColorUtils.strip_ansi(super().format(record))
