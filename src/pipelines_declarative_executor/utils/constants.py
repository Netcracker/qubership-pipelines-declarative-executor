class Constants:
    PIPELINE_STATE_DIR_NAME = "pipeline_state"
    PIPELINE_OUTPUT_DIR_NAME = "pipeline_output"
    PIPELINE_BACKUP_DIR_NAME = "pipeline_backup"
    PIPELINE_DEBUG_DIR_NAME = "x_debug"
    DEBUG_STAGE_LOGS_DIR_NAME = "stage_logs"

    STATE_EXECUTION_FILE_NAME = "execution.json"
    STATE_PIPELINE_FILE_NAME = "pipeline.json"
    STATE_VARS_FILE_NAME = "vars.json"
    PIPELINE_REPORT_FILE_NAME = "pipeline_report.json"

    STAGE_INPUT_FILES_DIR_NAME = "input_files"
    STAGE_OUTPUT_FILES_DIR_NAME = "output_files"
    STAGE_LOGS_DIR_NAME = "logs"
    STAGE_REPORT_JSON_FILE_NAME = "module_report.json"
    STAGE_REPORT_YAML_FILE_NAME = "module_report.yaml"
    PIPELINE_REPORT_FOR_REPORT_STAGE_FILE_NAME = "pipeline_report.json"

    DEFAULT_MASKED_VALUE = "*****"


class StatusCodes:
    PIPELINE_FINISHED_SUCCESS = "DEVOPS-STNDLN-EXEC-0000"
    PIPELINE_FINISHED_FAILURE = "DEVOPS-STNDLN-EXEC-0001"
    PIPELINE_FINISHED_UNKNOWN = "DEVOPS-STNDLN-EXEC-8888"
