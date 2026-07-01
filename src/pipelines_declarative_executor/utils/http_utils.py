import threading, logging, requests


class HttpUtils:
    """Shared, lazily-created requests.Session plus a cache of fetched remote bodies keyed by URL."""

    _session: requests.Session | None = None
    _lock = threading.Lock()

    _content_cache: dict[str, str] = {}
    _content_lock = threading.Lock()

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls._session is None:
            with cls._lock:
                if cls._session is None:
                    cls._session = requests.Session()
        return cls._session

    @classmethod
    def get_url_content(cls, url: str) -> str:
        with cls._content_lock:
            if url in cls._content_cache:
                return cls._content_cache[url]
        content = cls._fetch(url)
        with cls._content_lock:
            cls._content_cache[url] = content
        return content

    @classmethod
    def _fetch(cls, url: str) -> str:
        from pipelines_declarative_executor.utils.auth_utils import AuthConfig
        from pipelines_declarative_executor.utils.string_utils import StringUtils
        session = cls.get_session()
        auth_info = AuthConfig().get_auth_for_url(url)
        if auth_info:
            auth_data, auth_type, is_gitlab_url = auth_info
            logging.debug(f"Using {auth_type} authentication for {url}")
            if is_gitlab_url:
                url, body = StringUtils.parse_gitlab_raw_url_to_file_api(url, auth_data=auth_data)
                if body is not None:
                    return body
            if isinstance(auth_data, dict):
                response = session.get(url, headers=auth_data)
            else:
                response = session.get(url, auth=auth_data)
        else:
            response = session.get(url)
        response.raise_for_status()
        return response.text
