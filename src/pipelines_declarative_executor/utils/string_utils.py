from __future__ import annotations

import os, logging, re, dataclasses, requests

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote
from pipelines_declarative_executor.utils.constants import Constants


class StringUtils:
    @staticmethod
    def trim_lines(multiline: str) -> list[str]:
        return [trimmed_ln for ln in re.split(r'[\n\r;]', multiline) if (trimmed_ln := ln.strip())]

    @staticmethod
    def cast_to_string(value, value_for_none: str = '') -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return value_for_none
        if isinstance(value, bool):
            return 'true' if value else 'false'
        return str(value)

    VAR_PATTERN = re.compile(r'\$\{([a-zA-Z_]\w*)\}|\$([a-zA-Z_]\w*)')
    VAR_MAX_NESTING_LEVEL = 100
    @staticmethod
    def substitute_string(known_vars=None, *, expression=None, secure_keys=None, mask_secrets=False) -> tuple[str, bool]:
        if known_vars is None:
            known_vars = os.environ
        if secure_keys is None:
            secure_keys = ()
        if not isinstance(expression, str):
            return StringUtils.cast_to_string(expression), False
        description = f"expression '{expression}'"
        value = expression
        used_secure = False
        def _replace(m):
            nonlocal used_secure
            key = m[1] or m[2]
            if key in secure_keys:
                used_secure = True
                if mask_secrets:
                    return Constants.DEFAULT_MASKED_VALUE
            return StringUtils.cast_to_string(known_vars.get(key))
        for _ in range(StringUtils.VAR_MAX_NESTING_LEVEL):
            value, repl_n = re.subn(StringUtils.VAR_PATTERN, _replace, value)
            if not repl_n:
                return value, used_secure
        raise ValueError(f"Variables substitution exceeded {StringUtils.VAR_MAX_NESTING_LEVEL} nesting levels for {description}")

    @staticmethod
    def get_duration_str(start_time: datetime, finish_time: datetime) -> str:
        if not (start_time and finish_time):
            return "N/A"
        seconds = int((finish_time - start_time).total_seconds())
        parts = [seconds / 3600, (seconds % 3600) / 60, seconds % 60]
        strings = list(map(lambda x: str(int(x)).zfill(2), parts))
        return ":".join(strings)

    @staticmethod
    def duration_str_to_seconds(duration_str: str) -> float:
        duration_str = duration_str.strip()
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([smh])?$', duration_str)
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}")
        value = float(match.group(1))
        unit = match.group(2) if match.group(2) else 's'
        multipliers = {'s': 1, 'm': 60, 'h': 3600}
        return value * multipliers[unit]

    UNSAFE_FILENAME_CHARS_PATTERN = re.compile(r'[^\w\-.]')
    @staticmethod
    def get_safe_filename(s: str) -> str:
        return re.sub(StringUtils.UNSAFE_FILENAME_CHARS_PATTERN, '_', s)

    @staticmethod
    def json_encode(value):
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Path):
            return value.as_posix()
        elif isinstance(value, set):
            return list(value)
        logging.warning("can't serialize " + str(value))
        return str(value)

    @staticmethod
    def to_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    @staticmethod
    def parse_gitlab_raw_url_to_file_api(raw_url: str, auth_data) -> tuple[str, str | None]:
        """
        Convert GitLab UI URL to raw file API URL.
        Handles /-/raw/, /-/blob/, /-/tree/ URLs and branches with slashes.
        Uses trial-and-error to find the correct branch/file path split.
        Returns a (resolved_url, body) tuple: the resolved file-API URL, and the body already
        fetched by the successful probe so the caller can skip re-fetching it. body is None when
        no probe succeeded (URL left unchanged), in which case the caller must fetch it.
        """
        parsed = urlparse(raw_url)
        path = parsed.path

        patterns = [
            r'^(.*?)/-/raw/(.+)$',
            r'^(.*?)/-/blob/(.+)$',
            r'^(.*?)/-/tree/(.+)$',
        ]

        from pipelines_declarative_executor.utils.http_utils import HttpUtils
        session = HttpUtils.get_session()
        for pattern in patterns:
            match = re.match(pattern, path)
            if match:
                project_path = match.group(1).strip('/')
                branch_and_file = match.group(2)

                parts = branch_and_file.split('/')
                for split_point in range(1, len(parts)):
                    potential_branch = '/'.join(parts[:split_point])
                    potential_file_path = '/'.join(parts[split_point:])

                    if not potential_file_path:
                        continue

                    test_api_url = (
                        f"{parsed.scheme}://{parsed.netloc}/api/v4/projects/"
                        f"{quote(project_path, safe='')}/repository/files/"
                        f"{quote(potential_file_path, safe='')}/raw?ref={quote(potential_branch, safe='')}"
                    )

                    try:
                        if isinstance(auth_data, dict):
                            response = session.get(test_api_url, headers=auth_data)
                        else:
                            response = session.get(test_api_url, auth=auth_data)
                        if response.status_code == 200:
                            return test_api_url, response.text
                    except requests.RequestException:
                        continue

        return raw_url, None

    @staticmethod
    def normalize_line_endings(text: str) -> str:
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        return text

    @staticmethod
    def mask_value(key = None, value = None) -> str:
        if value is None or value == '':
            return ""
        return Constants.DEFAULT_MASKED_VALUE

    @staticmethod
    def indent_lines(text: str, indent: str = Constants.STAGE_OUTPUT_LOG_INDENT) -> str:
        if not text:
            return text
        return "\n".join(indent + line for line in text.splitlines())

    @staticmethod
    def format_pipeline_header(text: str, width: int = 120, indent: str = "    ") -> str:
        if not text:
            return text
        top_border = "┌" + "─" * width
        bottom_border = "└" + "─" * width
        prefix = "│ "

        lines = text.splitlines()
        result = [indent + top_border]
        for line in lines:
            result.append(indent + prefix + line)
        result.append(indent + bottom_border)
        return "\n".join(result)

    @staticmethod
    def shorten_command(command: str, max_len: int = 30) -> str:
        if not command:
            return command
        lines = [ln for ln in (line.strip() for line in StringUtils.normalize_line_endings(command).split('\n')) if ln]
        if len(lines) <= 1 and len(command) <= max_len:
            return command
        trimmed = '; '.join(lines)
        if len(trimmed) > max_len:
            trimmed = trimmed[:max_len].rstrip() + '...'
        return trimmed
