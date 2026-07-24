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
    _ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[mK]')
    _CI_GL_SECTION_START = re.compile(r'(?:\x1b\[0K)?section_start:\d+:[^\r\[\n]+(?:\[[^\]]*\])?(?:\r(?:\x1b\[0K)?)?')
    _CI_GL_SECTION_END = re.compile(r'(?:\x1b\[0K)?section_end:\d+:[^\r\n]*(?:\r(?:\x1b\[0K)?)?')
    _CI_GL_CLEAR_ONLY = re.compile(r'^(?:\x1b\[0K)+\s*$')

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
        return ColorUtils._ANSI_PATTERN.sub('', text)

    @staticmethod
    def strip_ci_sections(text: str) -> str:
        if '::group::' not in text and '::endgroup::' not in text and 'section_start:' not in text and 'section_end:' not in text:
            return text

        out_lines = []
        for line in text.split('\n'):
            if line.strip() == '::endgroup::':
                continue
            stripped_end = ColorUtils._CI_GL_SECTION_END.sub('', line)
            if stripped_end != line and stripped_end.strip() == '':
                continue
            line = stripped_end
            stripped_start = ColorUtils._CI_GL_SECTION_START.sub('', line)
            if stripped_start != line and stripped_start.strip() == '':
                continue
            line = stripped_start
            if ColorUtils._CI_GL_CLEAR_ONLY.match(line):
                continue
            if line.startswith('::group::'):
                line = line[len('::group::'):]
            out_lines.append(line)
        return '\n'.join(out_lines)


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
    """Strips ANSI colors and CI collapsible-section markers for clean file/plain logs."""

    def format(self, record):
        formatted = super().format(record)
        formatted = ColorUtils.strip_ci_sections(formatted)
        return ColorUtils.strip_ansi(formatted)
