## Configurable ENV Properties

### General Params

| Name                                                       |          Default Value          | Comment                                                                                              |
|------------------------------------------------------------|:-------------------------------:|------------------------------------------------------------------------------------------------------|
| PIPELINES_DECLARATIVE_EXECUTOR_GLOBAL_CONFIGS_PREFIX       |      CUSTOM_GLOBAL_CONFIG       | Env Vars with this prefix will be treated as AtlasConfigs                                            |
| PIPELINES_DECLARATIVE_EXECUTOR_SHELL_PROCESS_TIMEOUT       |               30                | Timeout in seconds for invoked shell subprocesses                                                    |
| PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_FULL_EXECUTION_LOG   |              True               | Enables full process debug-logging in workdir                                                        |
| PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_PROFILER_STATS       |              False              | Enables profiler stats (dumped to log at the end of execution) (also logs stage execution timing)    |
| PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_MODULE_STDOUT_LOG    |              True               | Enables logging of invoked shell commands stdout (including "Python Modules")                        |
| PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_DEBUG_DATA_COLLECTOR |              True               | Enables debug data collection after pipeline execution (available in 'x_debug' directory)            |
| PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH          |              None               | Path to .PYZ or unzipped folder with "Python Module" Commands (automatically set in Docker image)    |
| PIPELINES_DECLARATIVE_EXECUTOR_AUTH_RULES_FILE_PATH        |              None               | Path to file with JSON string with Auth Rules config (will be checked here first)                    |
| PIPELINES_DECLARATIVE_EXECUTOR_AUTH_RULES                  |              None               | JSON string with Auth Rules config (sample is in [config examples](./config_examples.md#auth_rules)) |

### Resource Manager Params

| Name                                                          |          Default Value          | Comment                                                                                                        |
|---------------------------------------------------------------|:-------------------------------:|----------------------------------------------------------------------------------------------------------------|
| PIPELINES_DECLARATIVE_EXECUTOR_ENABLE_RESOURCE_MANAGER        |              True               | Enables "Resource Manager" which limits running subprocesses in parallel                                       |
| PIPELINES_DECLARATIVE_EXECUTOR_MAX_CONCURRENT_STAGES          | {Number of available CPU cores} | Limits how many subprocesses with "Python Modules" might be processes concurrently                             |
| PIPELINES_DECLARATIVE_EXECUTOR_REQUIRED_MEMORY_PER_SUBPROCESS |               100               | Average memory footprint of invoked CLIs in megabytes, used to limit invocations when not having enough memory |
| PIPELINES_DECLARATIVE_EXECUTOR_RESOURCE_MANAGER_QUEUE_TIMEOUT |               360               | Timeout in seconds for "Python Module" stages to wait for resources acquisition                                |

### SOPS Encryption Params

| Name                                                        | Default Value | Comment                                                                                                         |
|-------------------------------------------------------------|:-------------:|-----------------------------------------------------------------------------------------------------------------|
| PIPELINES_DECLARATIVE_EXECUTOR_FAIL_ON_MISSING_SOPS         |     True      | Whether config parsing should fail (or just ignore it) if we encounter SOPS-encrypted file and can't decrypt it |
| PIPELINES_DECLARATIVE_EXECUTOR_ENCRYPT_OUTPUT_SECURE_PARAMS |     True      | Whether resulting pipeline's `output_params_secure.yaml` should be SOPS-encrypted                               |
| SOPS_AGE_RECIPIENTS                                         |     None      | SOPS Public key (used for for encryption)                                                                       |
| SOPS_AGE_KEY                                                |     None      | SOPS Private key (used for for decryption)                                                                      |
| PIPELINES_DECLARATIVE_EXECUTOR_SOPS_PROCESS_TIMEOUT         |      10       | Timeout in seconds for invoked SOPS encryption/decryption subprocesses                                          |

### Executor Wrapper Params

| Name                                           | Default Value | Comment                                          |
|------------------------------------------------|:-------------:|--------------------------------------------------|
| PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_URL   |     None      | URL of execution instance to be used in report   |
| PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_USER  |     None      | User who triggered execution instance            |
| PIPELINES_DECLARATIVE_EXECUTOR_EXECUTION_EMAIL |     None      | Email of a user who triggered execution instance |

### Report Params

| Name                                                             | Default Value | Comment                                                                                                                 |
|------------------------------------------------------------------|:-------------:|-------------------------------------------------------------------------------------------------------------------------|
| PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_MODE                  | ON_COMPLETION | Whether report should be sent when pipeline execution finishes (`ON_COMPLETION`) or periodically (`PERIODIC`)           |
| PIPELINES_DECLARATIVE_EXECUTOR_REPORT_SEND_INTERVAL              |       5       | Interval in seconds between report snapshot uploads to remote host                                                      |
| PIPELINES_DECLARATIVE_EXECUTOR_REPORT_STATUS_POLL_INTERVAL       |      0.5      | Interval in seconds between status checks of current running pipeline when `SEND_MODE` is set to `ON_COMPLETION`        |
| PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS_FILE_PATH |     None      | Path to file with JSON string with remote endpoint configs (will be checked here first)                                 |
| PIPELINES_DECLARATIVE_EXECUTOR_REPORT_REMOTE_ENDPOINTS           |     None      | JSON string with remote endpoint configs (sample is in [config examples](./config_examples.md#report_remote_endpoints)) |
