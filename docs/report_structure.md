## Pipeline Report Structure

Executor generates `pipeline_report.json` with data on execution process, intended to be used for display in UI systems.

This report follows a certain structure:

```json
{
  "kind": "AtlasPipelineReport",
  "apiVersion": "v2",
  "...general pipeline execution data...": "...",
  "performance": {"...": "..."},
  "config": ["..."],
  "stages": ["..."]
}
```

### General pipeline data

```json
{
  "id": "28423ecc-a273-4a0a-af27-46841a231429",
  "name": "Complex Parallel Pipeline",
  "status": "SUCCESS",
  "code": "DEVOPS-STNDLN-EXEC-0000",
  "startedAt": "2026-03-02T13:47:19.320755",
  "finishedAt": "2026-03-02T13:47:22.620702",
  "time": "00:00:03",
  "url": "https....",
  "user": "user_who_triggered_pipeline",
  "email": "email_of_a_user_who_triggered_pipeline"
}
```

### Performance data

```json
{
  "performance": {
    "peakMemory": "145.9 MB",
    "peakCpu": "244.5%"
  }
}
```

### Config data

Shows different configured variables with their sources

```json
[
  {
    "name": "IS_DRY_RUN",
    "value": false,
    "source": {
      "kind": "INPUT_VAR",
      "name": "CLI_INPUT"
    }
  },
  {
    "name": "STAGE_TYPE_PY",
    "value": "PYTHON_MODULE",
    "source": {
      "kind": "LOCAL_FILE",
      "path": "tests/pipeline_configs/debug_logs/pipeline_complex.yaml"
    }
  }
]
```

### Stage data

Shows related stage execution data.

`performance` field might be absent if no performance metrics were collected during the run (as defined by run configuration).

`customData` field is also optional and reserved for further extensions.

```json
[
  {
    "id": "dbd8926f-b56c-4dba-85f4-47c12ac2467c",
    "name": "Spam Before Parallel",
    "path": "quber_cli.pyz",
    "type": "PYTHON_MODULE",
    "command": "spam",
    "status": "SUCCESS",
    "startedAt": "2026-03-02T14:45:58.477374",
    "finishedAt": "2026-03-02T14:45:58.789852",
    "time": "00:00:00",
    "execDir": "x_local_main_folder/0_spam_before_parallel",
    "url": null,
    "input": {
      "params": {
        "params": {
          "param_count": "3"
        }
      },
      "params_secure": {
        "systems": {
          "qubership": {
            "token": "[MASKED]"
          }
        }
      },
      "files": {}
    },
    "output": {
      "params": {
        "RESULT_SPAM": "jellybean_chocolate_meadow"
      },
      "params_secure": {},
      "files": {}
    },
    "performance": {
      "peakMemory": "32.1 MB",
      "avgCpu": "36.1%"
    },
    "customData": {}
  }
]
```
