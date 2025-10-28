[![PyPI](https://img.shields.io/pypi/v/qubership-pipelines-declarative-executor)](https://pypi.org/project/qubership-pipelines-declarative-executor/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/qubership-pipelines-declarative-executor)
![Tests](https://github.com/Netcracker/qubership-pipelines-declarative-executor/actions/workflows/run-tests.yml/badge.svg)
![Repo Size](https://img.shields.io/github/repo-size/Netcracker/qubership-pipelines-declarative-executor)

# Qubership Pipelines Declarative Executor

Open-source python pipelines orchestrator and executor.

This application is distributed as a library on PyPI, Docker image on GitHub Packages, and as a Reusable Workflow for your existing GitHub workflows.
You can use this application in any of the provided forms that best suits your needs.

## Structure

### Docker image

Provided Docker image with this application includes:

- Pipelines Declarative Executor app itself
- [Sample "Python Modules"](https://github.com/Netcracker/qubership-pipelines-cli-command-samples) to execute commands in your "Atlas Pipeline"
- SOPS binaries to securely process configuration files and output parameters

#### Using your own "Python Modules"

Sample "Python Modules", included in distributed Docker image, are only showcasing the intended way of working via Execution Commands and Execution Context.
You might need to have your custom commands executed in "Atlas Pipelines" - then you will need to create and distribute your own implementation.
There's a [Development Guide](https://github.com/Netcracker/qubership-pipelines-cli-command-samples/blob/main/docs/development.md) available in CLI Samples repository.

A few ways you can include your own "Python Modules" into executor Docker image:

- Building new [image](./Dockerfile) with required modules, and putting path to them to `PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH` env variable
- Mounting directory with your modules into the image, while also upgrading `PIPELINES_DECLARATIVE_EXECUTOR_PYTHON_MODULE_PATH` env variable to mounted path

Multiple "Python Modules" are supported via `stage.path` property ([check syntax guide for more information](docs/atlas_pipeline_syntax.md#module-path))

### Python Dependency

You can also use this application as a python dependency, by installing it from PyPI:

```bash
pip install qubership-pipelines-declarative-executor
```

Or adding it to your dependency list:

```python
qubership-pipelines-declarative-executor = "^2.0.0"
```

### Common CI Workflows (GitHub/GitLab)

Alternative usage scenario (although much less configurable than creating your own workflow, since we can't pass custom env variables into it) is using provided [Reusable Workflow](.github/workflows/reusable-pipeline.yml) in your repository.
There is an example of how it can be invoked from GitHub Workflow: [pipeline.yml](.github/workflows/pipeline.yml)

There's also an example of a similar implementation [for GitLab](docs/gitlab/.gitlab-ci.yml)

When you've created your own Docker image with necessary "Python Modules" (non-sample ones), you might want to create your own workflows using that image.
Provided workflows serve as a starting point, but custom workflows will allow full control and ability to pass env variables and local files.

## Features

### Atlas Pipeline definitions

"AtlasPipelines" are intended to work via Execution Commands, packed into ["Python Modules"](https://github.com/Netcracker/qubership-pipelines-cli-command-samples/blob/main/docs/development.md).

Pipeline itself describes data flow between sequentially executed stages, while also supporting invoking nested pipelines (for reusing configuration) and parallel stages.

This repository uses actual "AtlasPipelines" in its tests, you can [check them here](tests/pipeline_configs).

Separate article on syntax with examples [is available here](docs/atlas_pipeline_syntax.md).

### Reporting

Executor collects and can upload report (intended for UI representation) of currently executed pipeline.

This feature is configured via env variables in [Report section](docs/env_vars.md#report-params).
You can select `REPORT_SEND_MODE` (either `ON_COMPLETION` or `PERIODIC`), send intervals, and endpoint configs:

Report configuration [example is here](docs/config_examples.md#report_remote_endpoints)

### Auth Rules

Orchestrator can fetch remote AtlasPipeline and AtlasConfig files from various sources. To access private repositories or authenticated endpoints, you can configure **authentication rules**.

Example Auth Rules [are present here](docs/config_examples.md#auth_rules)

Rules are processed in order they are defined, and first applicable rule will be used (in case when multiple would've matched).

If no rules match, requests are made without authentication.

### CI Wrapper configuration

You can pass your CI (GitHub, GitLab, Jenkins, etc.) execution instance parameters (user who triggered pipeline, pipeline's URL) to make them available in the report via [environment variables](docs/env_vars.md#executor-wrapper-params)

### SOPS Encryption

Executor decrypts input files (pipelines and configs) if they are encrypted with [SOPS](https://getsops.io/), and can also encrypt any output secure files.
This feature is configured via a [set of environment variables](docs/env_vars.md#sops-encryption-params)

### ENV Configuration

Other parameters are available and documented in the [General section](docs/env_vars.md#general-params)

### Performance

Performance tests and comparisons of [different ways to invoke imported "Python Modules" will be available here](docs/performance.md)
