import uuid, os, requests, logging

from urllib.parse import urlparse
from requests import Response
from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.exceptions import SopsException
from pipelines_declarative_executor.model.pipeline import PipelineExecution, PipelineVars, Pipeline, Stage
from pipelines_declarative_executor.model.stage import ExecutionStatus, StageType
from pipelines_declarative_executor.utils.auth_utils import AuthConfig
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.sops_utils import SOPS, SopsUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


class PipelineOrchestrator:
    @staticmethod
    def prepare_pipeline_execution(pipeline_data: str, pipeline_vars: str = None) -> PipelineExecution:
        pipeline_execution = PipelineExecution(inputs={
            "pipeline_data": pipeline_data,
            "pipeline_vars": pipeline_vars,
        })
        vars_obj = PipelineVars()
        pipeline_dict, pipeline_path = None, None

        if pipeline_data:
            file_paths = StringUtils.trim_lines(pipeline_data)
            for file_path in file_paths:
                try:
                    data, is_secure, is_remote = PipelineOrchestrator._load_yaml_content(file_path=file_path)
                    kind = data.get('kind')
                    if kind == 'AtlasConfig':
                        config_params = {k: v for k, v in data.items() if k not in ('apiVersion', 'kind')}
                        for path, value in CommonUtils.traverse(config_params):
                            ParamsProcessor.set_config_var(vars_obj, path[-1], value, file_path, is_secure, is_remote)
                    elif kind == 'AtlasPipeline':
                        if pipeline_dict:
                            logging.warning(f"AtlasPipeline config already parsed from \"{pipeline_path}\", will ignore \"{file_path}\" - only one pipeline should be present")
                        else:
                            pipeline_dict, pipeline_path = data, file_path
                            if pipeline_embedded_vars := pipeline_dict.get('pipeline', {}).get('vars'):
                                ParamsProcessor.set_pipeline_vars(vars_obj, pipeline_embedded_vars, file_path, is_secure, is_remote)
                    else:
                        logging.warning(f"File {file_path} has unsupported kind: {kind}")
                except SopsException as e:
                    PipelineOrchestrator._process_sops_exception(e)
                except Exception as e:
                    logging.warning(f"Error processing file {file_path}: {str(e)}")

        if pipeline_vars:
            vars_list = StringUtils.trim_lines(pipeline_vars)
            for var in vars_list:
                if '=' in var:
                    key, value = var.split('=', 1)
                    ParamsProcessor.set_override_var(vars_obj, key.strip(), value.strip())

        PipelineOrchestrator._process_global_configs(vars_obj)

        if not pipeline_dict:
            raise Exception("No 'AtlasPipeline' present in 'pipeline_data'!")

        if EnvVar.ENCRYPT_OUTPUT_PARAMS:
            SOPS.init()

        pipeline_execution.pipeline = PipelineOrchestrator._create_pipeline_from_dict(pipeline_dict, vars_obj)
        pipeline_execution.vars = vars_obj
        return pipeline_execution

    @staticmethod
    def _create_pipeline_from_dict(pipeline_dict: dict, vars_obj: PipelineVars) -> Pipeline:
        pipeline = Pipeline()
        pipeline_data = pipeline_dict.get('pipeline', {})
        jobs_templates = pipeline_data.get('jobs', {})

        # pipeline.id = pipeline_data.get('id')
        pipeline.id = str(uuid.uuid4())
        pipeline.name = pipeline_data.get('name', 'Atlas Pipeline')
        pipeline.configuration = pipeline_data.get('configuration', {})

        for stage_index, stage_data in enumerate(pipeline_data.get('stages', [])):
            stage = PipelineOrchestrator._create_stage(stage_index, stage_data, jobs_templates, vars_obj)
            pipeline.stages.append(stage)

        return pipeline

    @staticmethod
    def _create_stage(stage_index: int, stage_data: dict, jobs_templates: dict, vars_obj: PipelineVars) -> Stage:
        stage = Stage()
        job_template = {}
        if 'job' in stage_data:
            job_template = jobs_templates.get(vars_obj.calculate_expression(stage_data['job']), {})
        merged_stage_data = CommonUtils.recursive_merge(job_template, stage_data)

        for field_name in ['name', 'type', 'path', 'command']:
            if value := merged_stage_data.get(field_name):
                setattr(stage, field_name, vars_obj.calculate_expression(value))

        if not stage.path:
            stage.path = EnvVar.PYTHON_MODULE_PATH

        for field_name in ['input', 'output']:
            if value := merged_stage_data.get(field_name):
                setattr(stage, field_name, value)
        stage.evaluated_params = {}

        if when := merged_stage_data.get('when'):
            if when_condition := when.get('condition'):
                stage.when.condition = when_condition
            if when_statuses := when.get('statuses'):
                stage.when.statuses = ExecutionStatus.list_from_string(when_statuses)

        if not stage.name:
            stage.name = "Nameless Stage"
        stage.id = StringUtils.get_safe_filename(f"{stage_index}_{stage.name.lower()}")
        stage.uuid = str(uuid.uuid4())

        if parallel_block := merged_stage_data.get('parallel', []):
            if isinstance(parallel_block, dict):
                parallel_block = list(parallel_block.values())
            stage.nested_parallel_stages = []
            stage.type = StageType.PARALLEL_BLOCK
            for nested_stage_index, nested_stage_data in enumerate(parallel_block):
                nested_stage = PipelineOrchestrator._create_stage(nested_stage_index, nested_stage_data,
                                                                  jobs_templates, vars_obj)
                stage.nested_parallel_stages.append(nested_stage)

        return stage

    @staticmethod
    def _process_global_configs(vars_obj: PipelineVars):
        global_configs_prefix = EnvVar.GLOBAL_CONFIGS_PREFIX
        for env_key, env_value in os.environ.items():
            if env_key.startswith(global_configs_prefix):
                try:
                    data, is_secure = SopsUtils.load_and_decrypt_yaml(env_value)
                    kind = data.get('kind')
                    if kind != 'AtlasConfig':
                        logging.warning(f"Global Config in env var '{env_key}' has unsupported kind: {kind}")
                        continue
                    config_params = {k: v for k, v in data.items() if k not in ('apiVersion', 'kind')}
                    for path, value in CommonUtils.traverse(config_params):
                        ParamsProcessor.set_global_config_var(vars_obj, path[-1], value, env_key, is_secure)
                except SopsException as e:
                    PipelineOrchestrator._process_sops_exception(e)
                except Exception as e:
                    logging.warning(f"Error loading Global Config YAML from '{env_key}' env var: {str(e)}")

    @staticmethod
    def _load_yaml_content(file_path: str) -> tuple[dict, bool, bool]:  # data, is_secure, is_remote
        try:
            url_components = urlparse(file_path)
            if url_components.scheme in ('http', 'https'):
                response = PipelineOrchestrator._get_response_from_url(file_path, AuthConfig().get_auth_for_url(file_path))
                data, is_secure = SopsUtils.load_and_decrypt_yaml(response.text)
                return data, is_secure, True
            else:
                with open(file_path, 'r') as f:
                    data, is_secure = SopsUtils.load_and_decrypt_yaml(f.read())
                    return data, is_secure, False
        except Exception as e:
            logging.warning(f"Error loading YAML from {file_path}: {str(e)}")
            raise

    @staticmethod
    def _get_response_from_url(url: str, auth_info: tuple[dict, str, bool] | None) -> Response:
        if auth_info:
            auth_data, auth_type, is_gitlab_url = auth_info
            logging.debug(f"Using {auth_type} authentication for {url}")
            if is_gitlab_url:
                url = StringUtils.parse_gitlab_raw_url_to_file_api(url, auth_data=auth_data)
            if isinstance(auth_data, dict):
                response = requests.get(url, headers=auth_data)
            else:
                response = requests.get(url, auth=auth_data)
        else:
            response = requests.get(url)
        response.raise_for_status()
        return response

    @staticmethod
    def _process_sops_exception(ex: SopsException):
        logging.error(f"Sops Exception: {ex}")
        if EnvVar.FAIL_ON_MISSING_SOPS:
            raise
