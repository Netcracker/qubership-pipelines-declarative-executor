## Example configurations

### REMOTE_DELIVERIES

This configuration will be read either from file, located in file path, specified in `PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES_FILE_PATH` env var,
or as a string value from `PIPELINES_DECLARATIVE_EXECUTOR_REMOTE_DELIVERIES` env var.

Each delivery describes one payload type (`status`, `report`, or `log`), how often to send it, and where.

| Delivery field     | Required                         | Description                                              |
|--------------------|----------------------------------|----------------------------------------------------------|
| `payload`          | yes                              | `status`, `report`, or `log`                             |
| `mode`             | yes                              | `periodic` or `on_completion` (case-insensitive)         |
| `interval_seconds` | when `mode` is `periodic`        | Minimum seconds between sends                            |
| `endpoints`        | yes                              | Non-empty list of HTTP or S3 targets                     |

`use_compression` is **required** on every endpoint.
If `use_compression` is `true`, the request body is GZIP compressed and `Content-Encoding: gzip` is added to HTTP headers.

Auth (for basic auth) requires both `username` and `password`, provided via `username_value` / `password_value` or `username_env_var` / `password_env_var`.
Token for substitution in `headers` can be provided via `token_value` or `token_env_var`.

```json
[
  {
    "payload": "status | report",
    "mode": "periodic",
    "interval_seconds": 10,
    "endpoints": [
      {
        "type": "http",
        "endpoint": "http://operator/api/v1/runs/<run-id>/deliveries/status",
        "headers": {
          "Authorization": "Bearer {token}",
          "Content-Type": "application/json"
        },
        "token_env_var": "PDE_OPERATOR_TOKEN",
        "use_compression": false
      }
    ]
  },
  {
    "payload": "log",
    "mode": "periodic",
    "interval_seconds": 10,
    "endpoints": [
      {
        "type": "http",
        "endpoint": "http://operator/api/v1/runs/<run-id>/deliveries/log",
        "headers": {
          "Authorization": "Bearer {token}",
          "Content-Type": "text/plain"
        },
        "token_env_var": "PDE_OPERATOR_TOKEN",
        "use_compression": true
      }
    ]
  },
  {
    "payload": "report",
    "mode": "on_completion",
    "endpoints": [
      {
        "type": "http",
        "endpoint": "https://api.example.com/report",
        "auth": {"username_value": "user", "password_value": "pass"},
        "headers": {"Content-Type": "application/json"},
        "use_compression": false
      }
    ]
  },
  {
    "payload": "report",
    "mode": "on_completion",
    "endpoints": [
      {
        "type": "s3",
        "host": "s3.example-minio.com",
        "access_key": "your_access_key",
        "secret_key": "your_secret_key",
        "bucket_name": "your_bucket",
        "object_name": "your_object",
        "use_compression": false
      }
    ]
  }
]
```

### AUTH_RULES

Available Auth Rules configuration values are described in following tables.

#### All types

| Name          | Example Values                       | Description                                                                    |
|---------------|--------------------------------------|--------------------------------------------------------------------------------|
| host          | githubusercontent.com/some_project/* | Value with wildcards support                                                   |
| type          | no_auth / token / basic              | How provided values will be used in executed web request                       |
| is_gitlab_url | true / false                         | Whether raw URL will be transformed into gitlab-specific API URL to fetch file |

#### Token type only

| Name          | Example Values                      | Description                                                                               |
|---------------|-------------------------------------|-------------------------------------------------------------------------------------------|
| headers       | {"Authorization": "Bearer {token}"} | Object/dict that will be added to request headers, can use {token} template inside values |
| token_value   | my_secret_token                     | Value of token (if you decide to store it in configuration, not in another ENV variable)  |
| token_env_var | MY_TOKEN_ENV_VAR                    | Name of ENV var where token will be taken from                                            |

#### Basic type only

| Name             | Example Values      | Description                                                                                 |
|------------------|---------------------|---------------------------------------------------------------------------------------------|
| username_value   | username            | Value of username (if you decide to store it in configuration, not in another ENV variable) |
| username_env_var | MY_USERNAME_ENV_VAR | Name of ENV var where username will be taken from                                           |
| password_value   | password            | Value of password (if you decide to store it in configuration, not in another ENV variable) |
| password_env_var | MY_PASSWORD_ENV_VAR | Name of ENV var where password will be taken from                                           |

This configuration will be read either from file, located in file path, specified in `PIPELINES_DECLARATIVE_EXECUTOR_AUTH_RULES_FILE_PATH` env var,
or as a string value from `PIPELINES_DECLARATIVE_EXECUTOR_AUTH_RULES` env var.

```json
[
  {
    "host": "gitlab.com/ProjectOne/*",
    "type": "token",
    "headers": {
      "PRIVATE-TOKEN": "{token}"
    },
    "token_env_var": "PROJECT_ONE_TOKEN",
    "is_gitlab_url": true
  },
  {
    "host": "gitlab.com/ProjectTwo/specific/path/*",
    "type": "token",
    "headers": {
      "PRIVATE-TOKEN": "{token}",
      "X-Project": "ProjectTwo"
    },
    "token_value": "QWERTY123",
    "is_gitlab_url": true
  },
  {
    "host": "gitlab.com",
    "type": "no_auth",
    "is_gitlab_url": true
  },
  {
    "host": "*.example.com/api/v1/*",
    "type": "basic",
    "username_env_var": "API_V1_USER",
    "password_env_var": "API_V1_PASS"
  },
  {
    "host": "*.example.com/api/v2/*",
    "type": "basic",
    "username_value": "example_user",
    "password_value": "example_pass"
  },
  {
    "host": "*.example.com",
    "type": "token",
    "headers": {
      "Authorization": "Bearer {token}"
    },
    "token_env_var": "INTERNAL_TOKEN"
  }
]
```
