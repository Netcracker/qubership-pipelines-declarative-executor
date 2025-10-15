## Example configurations

### REPORT_REMOTE_ENDPOINTS

This configuration will be read either from file, located in file path, specified in `PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS_FILE_PATH` env var,
or as a string value from `PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS` env var.

You can currently specify both `headers` and `auth` sections.
Auth (for basic auth) will require both `username` and `password`, they can be provided via `username_value` directly in config, or as name of env var - `username_env_var`.
Token for substitution in `headers` can also be provided via these approaches.

```json
[
  {
    "type": "http",
    "endpoint": "https://api.example.com",
    "auth": {"username_value": "user", "password_value": "pass"},
    "headers": {"Content-Type": "application/json"}
  },
  {
    "type": "http",
    "endpoint": "http://localhost:8000/send_report",
    "headers": {
      "Authorization": "Bearer {token}"
    },
    "token_value": "my_cool_token"
  },
  {
    "type": "http",
    "endpoint": "http://localhost:8000/send_report",
    "auth": {"username_value": "user", "password_env_var": "MY_PASSWORD_ENV_VAR"},
    "headers": {
      "x-SPECIAL-HEADER": "token {token}"
    },
    "token_env_var": "MY_SPECIAL_TOKEN_ENV_VAR"
  },
  {
    "type": "s3",
    "host": "s3.example-minio.com",
    "access_key": "your_access_key",
    "secret_key": "your_secret_key",
    "bucket_name": "your_bucket",
    "object_name": "your_object"
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
