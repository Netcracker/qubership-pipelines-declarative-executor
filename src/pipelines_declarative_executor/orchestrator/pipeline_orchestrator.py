import uuid, os, requests, logging

from urllib.parse import urlparse
from requests import Response
from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.exceptions import SopsException
from pipelines_declarative_executor.model.orchestrator import AtlasMetaFile, PipelineTemplate
from pipelines_declarative_executor.model.pipeline import PipelineExecution, PipelineVars, Pipeline, Stage
from pipelines_declarative_executor.model.stage import ExecutionStatus, StageType, VALID_STAGE_TYPES
from pipelines_declarative_executor.utils.auth_utils import AuthConfig
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.sops_utils import SOPS, SopsUtils
from pipelines_declarative_executor.utils.string_utils import StringUtils


class PipelineOrchestrator:
    @staticmethod
    def prepare_pipeline_execution(pipeline_data: str, pipeline_vars: str = None, pipeline_vars_secure: str = None) -> PipelineExecution:
        pipeline_execution = PipelineExecution(inputs={
            "pipeline_data": pipeline_data,
            "pipeline_vars": pipeline_vars,
            "pipeline_vars_secure": pipeline_vars_secure,
        })
        vars_obj = PipelineVars()
        merged_template = PipelineTemplate()
        last_pipeline = None

        if pipeline_data:
            for file_path in StringUtils.trim_lines(pipeline_data):
                try:
                    meta_file = PipelineOrchestrator._load_yaml_content(file_path=file_path)
                    kind = meta_file.data.get('kind')
                    if kind == 'AtlasConfig':
                        PipelineOrchestrator._process_atlas_config(vars_obj, meta_file)
                    elif kind == 'AtlasPipeline':
                        if last_pipeline:
                            logging.warning(f"AtlasPipeline from \"{last_pipeline.file_path}\" will be ignored - will use last one found in PIPELINE_DATA")
                        last_pipeline = meta_file
                    elif kind == 'AtlasPipelineTemplate':
                        PipelineOrchestrator._process_pipeline_template(merged_template, vars_obj, meta_file)
                    else:
                        logging.warning(f"File {meta_file.file_path} has unsupported kind: {kind}")
                except SopsException as e:
                    PipelineOrchestrator._process_sops_exception(e)
                except Exception as e:
                    logging.warning(f"Error processing file {file_path}: {str(e)}")

        if not last_pipeline:
            raise Exception("No 'AtlasPipeline' present in 'pipeline_data'!")

        if pipeline_embedded_vars := last_pipeline.data.get('pipeline', {}).get('vars'):
            ParamsProcessor.set_pipeline_embedded_vars(vars_obj, pipeline_embedded_vars, last_pipeline.file_path, last_pipeline.is_secure, last_pipeline.is_remote)
        if pipeline_vars:
            PipelineOrchestrator._process_pipeline_vars(vars_obj, pipeline_vars, is_secure=False)
        if pipeline_vars_secure:
            PipelineOrchestrator._process_pipeline_vars(vars_obj, pipeline_vars_secure, is_secure=True)

        PipelineOrchestrator._process_global_configs(vars_obj)

        if EnvVar.ENCRYPT_OUTPUT_PARAMS:
            SOPS.init()

        pipeline_execution.pipeline = PipelineOrchestrator._create_pipeline_from_dict(last_pipeline.data, vars_obj, merged_template)
        pipeline_execution.vars = vars_obj
        return pipeline_execution

    @staticmethod
    def _process_atlas_config(vars_obj: PipelineVars, config: AtlasMetaFile):
        config_params = {k: v for k, v in config.data.items() if k not in ('apiVersion', 'kind')}
        for path, value in CommonUtils.traverse(config_params):
            ParamsProcessor.set_config_var(vars_obj, path[-1], value, config.file_path, config.is_secure, config.is_remote)

    @staticmethod
    def _process_pipeline_template(merged_template: PipelineTemplate, vars_obj: PipelineVars, template: AtlasMetaFile):
        if template_vars := template.data.get('pipeline', {}).get('vars'):
            ParamsProcessor.set_pipeline_embedded_vars(vars_obj, template_vars, template.file_path, template.is_secure, template.is_remote)
        if template_config := template.data.get('pipeline', {}).get('configuration'):
            merged_template.configuration.update(template_config)
        if template_jobs := template.data.get('pipeline', {}).get('jobs'):
            merged_template.job_templates.update(template_jobs)

    @staticmethod
    def _process_pipeline_vars(vars_obj: PipelineVars, pipeline_vars: str, is_secure: bool = False):
        vars_list = StringUtils.trim_lines(pipeline_vars)
        for var in vars_list:
            if '=' in var:
                key, value = var.split('=', 1)
                ParamsProcessor.set_override_var(vars_obj, key.strip(), value.strip(), is_secure)

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
    def _create_pipeline_from_dict(pipeline_dict: dict, vars_obj: PipelineVars, merged_template: PipelineTemplate) -> Pipeline:
        pipeline = Pipeline()
        pipeline_data = pipeline_dict.get('pipeline', {})
        jobs_templates = {**merged_template.job_templates, **pipeline_data.get('jobs', {})}

        pipeline.id = str(uuid.uuid4())
        pipeline.name = vars_obj.calculate_expression(pipeline_data.get('name', 'Atlas Pipeline'))
        pipeline.configuration = {**merged_template.configuration, **pipeline_data.get('configuration', {})}

        flattened_stages = PipelineOrchestrator._flatten_stage_dicts(pipeline_data.get('stages', []))
        for stage_index, stage_data in enumerate(flattened_stages):
            stage = PipelineOrchestrator._create_stage(stage_index, stage_data, jobs_templates, vars_obj)
            pipeline.stages.append(stage)

        return pipeline

    @staticmethod
    def _flatten_stage_dicts(stage_dicts: list) -> list:
        flattened = []
        for stage_dict in stage_dicts:
            if stages_block := stage_dict.get('stages', []):
                if any(key in stage_dict for key in ['job', 'type', 'parallel']):
                    container_name = stage_dict.get('name', 'stages-inside-stage')
                    logging.warning(f"Flattening \"{container_name}\" - has job/type/parallel properties that will be discarded (will only be used as a container!)")
                flattened.extend(PipelineOrchestrator._flatten_stage_dicts(stages_block))
            else:
                if parallel_block := stage_dict.get('parallel', []):
                    if isinstance(parallel_block, dict):
                        parallel_block = list(parallel_block.values())
                    stage_dict['parallel'] = PipelineOrchestrator._flatten_stage_dicts(parallel_block)
                flattened.append(stage_dict)
        return flattened

    @staticmethod
    def _create_stage(stage_index: int, stage_data: dict, jobs_templates: dict, vars_obj: PipelineVars) -> Stage:
        stage = Stage()
        job_template = {}
        if 'job' in stage_data:
            template_name = vars_obj.calculate_expression(stage_data['job'])
            job_template = jobs_templates.get(template_name)
            if not job_template:
                raise Exception(f"Missing job-template requested: {template_name}")
        merged_stage_data = CommonUtils.recursive_merge(job_template, stage_data)

        for field_name in ['name', 'type', 'path', 'command']:
            if value := merged_stage_data.get(field_name):
                setattr(stage, field_name, vars_obj.calculate_expression(value))

        if not stage.path:
            stage.path = EnvVar.PYTHON_MODULE_PATH

        for field_name in ['input', 'output']:
            if value := merged_stage_data.get(field_name):
                setattr(stage, field_name, value)

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
                nested_stage = PipelineOrchestrator._create_stage(nested_stage_index, nested_stage_data, jobs_templates, vars_obj)
                stage.nested_parallel_stages.append(nested_stage)

        if stage.type not in VALID_STAGE_TYPES:
            raise Exception(f"Unknown stage type: {stage.type} (in stage {stage.name} - {stage.id})")

        return stage

    @staticmethod
    def _load_yaml_content(file_path: str) -> AtlasMetaFile:
        try:
            url_components = urlparse(file_path)
            if url_components.scheme in ('http', 'https'):
                response = PipelineOrchestrator._get_response_from_url(file_path, AuthConfig().get_auth_for_url(file_path))
                data, is_secure = SopsUtils.load_and_decrypt_yaml(response.text)
                return AtlasMetaFile(data, file_path, is_secure, True)
            else:
                with open(file_path, 'r') as f:
                    data, is_secure = SopsUtils.load_and_decrypt_yaml(f.read())
                    return AtlasMetaFile(data, file_path, is_secure, False)
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
