## Atlas File Types

Orchestration supports loading pipelines and configuration from a variety of different Atlas file types:

- [AtlasPipeline](#atlaspipeline)
- [AtlasConfig](#atlasconfig)
- [AtlasPipelineTemplate](#atlaspipelinetemplate)

### AtlasPipeline

Mandatory descriptor of pipeline with its stages. Has separate [syntax documentation](./atlas_pipeline_syntax.md) available.

In case multiple AtlasPipelines are passed into orchestrator, only the last one will be used, and warning about other ones being ignored will appear.

```yaml
kind: AtlasPipeline
apiVersion: v2

pipeline:
  id: pipeline-1-cmd
  name: Simple 1-Cmd Pipeline
  vars:
    STAGE_TYPE_PY: PYTHON_MODULE

  stages:
    - name: Spam Cmd
      job: template-py-stage
      command: "spam"
      path: "optional/path/to/non-default-python-module"
      output:
        params:
          RESULT_SPAM: "params.some_insecure_param_3"

  jobs:
    template-py-stage:
      type: ${STAGE_TYPE_PY}

  configuration:
    output:
      params:
        params:
          CALC_RESULT: ${CALC_RESULT}
```

### AtlasConfig

Optional reusable descriptor for parameters.

Supports nesting parameters into different structures for organizing purpose, but **only last-level keys are used** when parsing these configurations, and that is the way to reference these parameters.

E.g. in below config, stored GitHub URL is available only via `${GH_URL}`, but **NOT** via `${github.params.GH_URL}`

In case multiple AtlasConfigs are passed into orchestrator, their parameters will be added to common context in order of appearance.

```yaml
kind: AtlasConfig
apiVersion: v1

global:
  vars:
    VAR_FROM_SIMPLE_CONFIG: 56
    ANOTHER_VAR: test

github:
  params:
    GH_URL: github.com
    test_github_token: test123
```

### AtlasPipelineTemplate

Optional descriptor of reusable stage-templates (`jobs`), `configuration`, and `vars`. These section in template follow same syntax rules as in `AtlasPipeline`.

In case multiple AtlasPipelineTemplates are passed into orchestrator, they will be applied in order of appearance. All templates are merged together before the `AtlasPipeline` is applied.

Only `vars`, `jobs` and `configuration` sections are merged and applied. Other sections of a template are ignored.

The merge is **top-level only** (shallow). For each section the executor iterates the top-level keys of every template and then the `AtlasPipeline`, last writer wins.

```yaml
kind: AtlasPipelineTemplate
apiVersion: v2

pipeline:
  vars:
    VAR_FROM_TEMPLATE: some_value
    STAGE_TYPE_PY: PYTHON_MODULE

  jobs:
    template-spam-stage:
      type: ${STAGE_TYPE_PY}
      command: "spam"
      input:
        params:
          params:
            param_count: 3

  configuration:
    output:
      params:
        params:
          SOME_COMMON_OUTPUT_PARAM: ${RESULT}
```
