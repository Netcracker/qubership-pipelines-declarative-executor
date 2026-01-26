from __future__ import annotations

import os, logging, re, dataclasses, requests

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, quote


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
    def substitute_string(known_vars=None, *, expression=None) -> str:
        if known_vars is None:
            known_vars = os.environ
        if not isinstance(expression, str):
            return StringUtils.cast_to_string(expression)
        description = f"expression '{expression}'"
        value = expression
        for _ in range(StringUtils.VAR_MAX_NESTING_LEVEL):
            value, repl_n = re.subn(StringUtils.VAR_PATTERN, lambda m: StringUtils.cast_to_string(known_vars.get(m[1] or m[2])), value)
            if repl_n:
                pass
            else:
                return value
        raise ValueError(f"Variables substitution exceeded {StringUtils.VAR_MAX_NESTING_LEVEL} nesting levels for {description}")

    @staticmethod
    def get_duration_str(start_time: datetime, finish_time: datetime) -> str:
        if not (start_time and finish_time):
            return "N/A"
        seconds = int((finish_time - start_time).total_seconds())
        parts = [seconds / 3600, (seconds % 3600) / 60, seconds % 60]
        strings = list(map(lambda x: str(int(x)).zfill(2), parts))
        return ":".join(strings)

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
    def parse_gitlab_raw_url_to_file_api(raw_url: str, auth_data) -> str:
        """
        Convert GitLab UI URL to raw file API URL.
        Handles /-/raw/, /-/blob/, /-/tree/ URLs and branches with slashes.
        Uses trial-and-error to find the correct branch/file path split.
        """
        parsed = urlparse(raw_url)
        path = parsed.path

        patterns = [
            r'^(.*?)/-/raw/(.+)$',
            r'^(.*?)/-/blob/(.+)$',
            r'^(.*?)/-/tree/(.+)$',
        ]

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
                            response = requests.get(test_api_url, headers=auth_data)
                        else:
                            response = requests.get(test_api_url, auth=auth_data)
                        if response.status_code == 200:
                            return test_api_url
                    except requests.RequestException:
                        continue

        return raw_url

    @staticmethod
    def normalize_line_endings(text: str) -> str:
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        return text
