import json, logging, fnmatch

from enum import StrEnum
from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth
from pipelines_declarative_executor.utils.env_var_utils import EnvVar, EnvVarUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


class AuthType(StrEnum):
    NO_AUTH = "no_auth"
    BASIC = "basic"
    TOKEN = "token"


class AuthConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rules = cls._instance._load_auth_rules()
        return cls._instance

    def get_auth_for_url(self, url: str) -> tuple[dict, str, bool] | None:
        for rule in self.rules:
            if self._url_matches(rule['host'], url):
                match auth_type := rule.get('type', ''):
                    case AuthType.NO_AUTH:
                        return self._handle_no_auth(rule, url)
                    case AuthType.BASIC:
                        return self._handle_basic_auth(rule, url)
                    case AuthType.TOKEN:
                        return self._handle_token_auth(rule, url)
                    case _:
                        logging.warning(f"Unknown auth_type: {auth_type} in rule {rule['host']}")
        return None

    @staticmethod
    def _load_auth_rules() -> list[dict]:
        rules_json = EnvVarUtils.load_config_from_file_or_from_value(EnvVar.AUTH_RULES_NAME)
        if not rules_json:
            return []
        try:
            return json.loads(rules_json)
        except json.JSONDecodeError as e:
            logging.warning(f"Failed to parse AUTH_RULES: {e}")
            return []

    @staticmethod
    def _url_matches(rule_pattern: str, target_url: str) -> bool:
        try:
            parsed_rule = urlparse(rule_pattern)
            parsed_target = urlparse(target_url)

            rule_host = parsed_rule.netloc or parsed_rule.path.split('/', 1)[0]
            if not rule_host.startswith("*"):
                rule_host = "*" + rule_host
            rule_path = parsed_rule.path if parsed_rule.netloc else ''

            target_host = parsed_target.netloc
            target_path = parsed_target.path

            if ':' in target_host:
                target_host = target_host.split(':', 1)[0]

            if not fnmatch.fnmatch(target_host, rule_host):
                return False

            if rule_path:
                rule_path = rule_path if rule_path.startswith('/') else '/' + rule_path
                target_path = target_path if target_path.startswith('/') else '/' + target_path
                return fnmatch.fnmatch(target_path, rule_path)

            return True
        except Exception:
            return False

    @staticmethod
    def _handle_token_auth(rule: dict, url: str) -> tuple[dict, str, bool] | None:
        token = EnvVarUtils.get_value_or_from_env(rule, 'token')
        if not token:
            logging.warning(f"Token for token-auth not found for URL: {url}")
            return None
        headers = {}
        for header_name, header_template in rule.get('headers', {}).items():
            header_value = header_template.format(token=token)
            headers[header_name] = header_value
        return headers, AuthType.TOKEN, StringUtils.to_bool(rule.get("is_gitlab_url", False))

    @staticmethod
    def _handle_basic_auth(rule: dict, url: str) -> tuple[HTTPBasicAuth, str, bool] | None:
        username = EnvVarUtils.get_value_or_from_env(rule, 'username')
        password = EnvVarUtils.get_value_or_from_env(rule, 'password')
        if not username or not password:
            logging.warning(f"Basic auth credentials not fully set for URL: {url}")
            return None
        return HTTPBasicAuth(username, password), AuthType.BASIC, StringUtils.to_bool(rule.get("is_gitlab_url", False))

    @staticmethod
    def _handle_no_auth(rule: dict, url: str) -> tuple[dict, str, bool] | None:
        return {}, AuthType.NO_AUTH, StringUtils.to_bool(rule.get("is_gitlab_url"))
