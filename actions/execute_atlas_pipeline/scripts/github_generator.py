import os
import re
import sys
from pathlib import Path

import requests
import yaml
from textwrap import dedent

# in entry point, configure logging before other imports that may write logs
import logging
logging.basicConfig(stream=sys.stdout,
                    format='[%(asctime)s] [%(levelname)-5s] [%(filename)s:%(lineno)-3s] %(message)s',
                    level=os.getenv('LOG_LEVEL') or logging.DEBUG)

from github_generator_utils import (get_id_or_name, cast_to_string, parse_params_from_string,
                                    substitute_string, traverse, recursive_merge, get_safe_gh_jobname)
logger = logging.getLogger(__name__)


def _trim_lines(multiline): return [trimmed_ln for ln in re.split(r'[\n\r;]', multiline) if (trimmed_ln:=ln.strip())]
def _dict_subset(src_dict, keys): return {k: src_dict[k] for k in keys if k in src_dict}

_GENERATOR_INCLUDE_ATLAS_STAGES =   os.getenv('GENERATOR_INCLUDE_ATLAS_STAGES', '')
_GENERATOR_ALLOW_FAILURE_ALL_JOBS = os.getenv('GENERATOR_ALLOW_FAILURE_ALL_JOBS', 'false')
_LOG_LEVEL = os.getenv('LOG_LEVEL')

_PIPELINE_DATA = os.getenv('PIPELINE_DATA', '')
_PIPELINE_VARS = os.getenv('PIPELINE_VARS', '')

_PASS_DOWNSTREAM_PARAM_NAMES = [
    'GENERATOR_ALLOW_FAILURE_ALL_JOBS', 'GENERATOR_ATLAS_JOB_VARS_PREFIX', 'LOG_LEVEL', 'DRY_RUN'
]

_ALL_PIPELINE_PARAM_NAMES = [
        'PIPELINE_DATA', 'PIPELINE_VARS',
        'GENERATOR_INCLUDE_ATLAS_STAGES',
        *_PASS_DOWNSTREAM_PARAM_NAMES,
]
_ALL_PIPELINE_PARAMS = _dict_subset(os.environ, _ALL_PIPELINE_PARAM_NAMES)

_PIPELINE_INFO_PARAM_NAMES = [
    'id', 'name'
]

logger.info('Pipeline has started with params:\n%s', yaml.safe_dump(_ALL_PIPELINE_PARAMS, sort_keys=False))


class AtlasPipelineData:
    def __init__(self):
        self._pipeline_descriptor = {}
        self._config_descriptors = []
        self._input_vars = {}

    def process_config(self, content: str):
        input_descriptor = yaml.safe_load(content)
        kind = input_descriptor.get('kind')
        if kind == 'AtlasPipeline':
            self._pipeline_descriptor = input_descriptor
        elif kind == 'AtlasConfig':
            self._config_descriptors.append(input_descriptor)
        else:
            raise ValueError(f"Unsupported kind '{kind}'")

    def process_params(self, content: str):
        self._input_vars.update(parse_params_from_string(content))

    def get_info(self) -> dict:
        info = {}
        if pipeline_descriptor_info := self._pipeline_descriptor.get('pipeline'):
            for param_name in _PIPELINE_INFO_PARAM_NAMES:
                if param := pipeline_descriptor_info.get(param_name):
                    info[param_name] = param
        return info

    def get_report_params(self) -> dict:
        return self._pipeline_descriptor.get('pipeline', {}).get('report', {})

    def get_vars(self) -> dict:
        all_vars = {}  # pipeline vars are overridden by config vars and then by input vars
        if pipeline_vars := self._pipeline_descriptor.get('pipeline', {}).get('vars'):  # may present but be None
            all_vars.update(pipeline_vars)
        for config_descriptor in self._config_descriptors:
            config_params = {k: v for k, v in config_descriptor.items() if k not in ('apiVersion', 'kind')}
            for path, value in traverse(config_params):
                all_vars[path[-1]] = value
        all_vars.update(self._input_vars)
        return all_vars

    def get_stages(self) -> list:
        return self._pipeline_descriptor.get('pipeline', {}).get('stages') or []

    def get_jobs(self) -> dict:
        return self._pipeline_descriptor.get('pipeline', {}).get('jobs') or {}

    def get_configuration(self) -> dict:
        return self._pipeline_descriptor.get('pipeline', {}).get('configuration') or {}


class GithubPipelineData:
    _WORKFLOW_NAME = "GENERATED_WORKFLOW"
    _COMMON_ENV_VARS = "GITHUB_COMMON_ENV_VARS"

    def __init__(self):
        self.pipeline_info = {}
        self.report_params = {}
        self.vars = {}
        self.jobs = {}
        self.job_templates = {}
        self._stages = {}
        self.add_var = self.vars.__setitem__
        self.add_job = self.jobs.__setitem__
        self.add_job_template = self.job_templates.__setitem__

    def register_stage(self, stage_id: str, job_id: str):
        if stage_id not in self._stages:
            self._stages[stage_id] = []
        self._stages[stage_id].append(job_id)

    def get_previous_stage_jobs(self):
        if len(self._stages) < 2:
            return []
        return self._stages[[*self._stages.keys()][-2]]

    def get_all_vars(self):
        return {
            **({'GITHUB_MODULES_OPS_LOG_LEVEL': _LOG_LEVEL} if _LOG_LEVEL else {}),
            **self.vars
        }

    def get_pipeline(self):
        pipeline = {
            'name': self._WORKFLOW_NAME,
            'on': {
                'workflow_dispatch': {}
            },
            'permissions': {
                'actions': 'read',
                'contents': 'read',
            }
        }
        if pipeline_name := self.pipeline_info.get("name"):
            pipeline['run-name'] = pipeline_name
        if common_env_vars := self.get_all_vars():
            pipeline['env'] = {
                self._COMMON_ENV_VARS: yaml.safe_dump(common_env_vars, sort_keys=False)
            }
        if self.jobs:
            pipeline['jobs'] = self.jobs
        return pipeline


class VarsCalculation:
    def __init__(self, known_vars: dict):
        self.known_vars = known_vars

    def calculate_expression(self, exp):
        return substitute_string(self.known_vars, expression=exp)

    def evaluate_expression(self, exp):
        return True == eval(exp, self.known_vars)

    def resolve_when_condition(self, when_condition: str):
        logger.debug(f"Resolving condition: [{when_condition}]")
        when_condition_with_substitutes = self.calculate_expression(when_condition)
        result = self.evaluate_expression(when_condition_with_substitutes)
        logger.debug(f"'{when_condition_with_substitutes}' -> {result}")
        return result


class PipelineConverter:
    _INCLUDE_ATLAS_STAGES = _trim_lines(_GENERATOR_INCLUDE_ATLAS_STAGES)
    _ALLOW_FAILURE_ALL_JOBS = _GENERATOR_ALLOW_FAILURE_ALL_JOBS == 'true'
    # REFS TO REUSABLE WORKFLOWS:
    _DEFAULT_MODULE_IMAGE_REUSABLE_FLOW = f'Netcracker/qubership-pipelines-declarative-executor/.github/workflows/_execute_image_module.yml@{os.getenv("EXECUTOR_REF")}'
    _SAVE_PIPELINE_OUTPUT_REUSABLE_FLOW = f'Netcracker/qubership-pipelines-declarative-executor/.github/workflows/_save_pipeline_output.yml@{os.getenv("EXECUTOR_REF")}'
    _DEFAULT_PREPARE_JOB_ID = 'prepare-common-vars'
    _DEFAULT_SAVE_JOB_ID = 'save-pipeline-output'
    _REQUIRED_ATLAS_STAGE_FIELDS = ["path", "type", "command", "name"]
    _PYTHON_DOCKER_IMAGE_TYPE = 'PYTHON_DOCKER_IMAGE'
    _REPORT_TYPE = 'REPORT'
    _SUPPORTED_JOB_TYPES = [_PYTHON_DOCKER_IMAGE_TYPE, _REPORT_TYPE]

    def __init__(self, atlas_pipeline_data: AtlasPipelineData):
        self.atlas_pipeline_data = atlas_pipeline_data
        self._atlas_vars = atlas_pipeline_data.get_vars()
        self._vars_calc = VarsCalculation(self._atlas_vars)
        self.gh_pipeline_data = GithubPipelineData()

    def convert_pipeline_info(self):
        self.gh_pipeline_data.pipeline_info = self.atlas_pipeline_data.get_info()
        self.gh_pipeline_data.report_params = self.atlas_pipeline_data.get_report_params()

    def convert_atlas_vars(self):
        for k, v in self._atlas_vars.items():
            self.gh_pipeline_data.add_var(k, cast_to_string(v))

    def convert_atlas_jobs_to_job_templates(self):
        for atlas_job_id, atlas_job in self.atlas_pipeline_data.get_jobs().items():
            self.gh_pipeline_data.add_job_template(atlas_job_id, atlas_job)

    def convert_atlas_stages_to_jobs(self):
        for atlas_stage in self.atlas_pipeline_data.get_stages():
            if atlas_parallel := atlas_stage.get('parallel', {}):
                for atlas_inner_stage_id, atlas_inner_stage in atlas_parallel.items():
                    enriched_inner_stage_data = self._enrich_atlas_stage(
                        atlas_inner_stage,
                        parent_stage_name=get_id_or_name(atlas_stage),
                        inner_stage_id=atlas_inner_stage_id)
                    self._add_job(enriched_inner_stage_data)
            else:
                enriched_stage_data = self._enrich_atlas_stage(atlas_stage)
                self._add_job(enriched_stage_data)

    def _enrich_atlas_stage(self, atlas_stage, parent_stage_name = None, inner_stage_id = None):
        if job_template := self.gh_pipeline_data.job_templates.get(atlas_stage.get('job')):
            data = recursive_merge(job_template, atlas_stage)
        else:
            data = atlas_stage

        for field in PipelineConverter._REQUIRED_ATLAS_STAGE_FIELDS:
            if field in data:
                data[field] = self._vars_calc.calculate_expression(data.get(field))

        if parent_stage_name:
            data["stage_id"] = get_safe_gh_jobname(parent_stage_name)
            data["job_id"] = f"{data['stage_id']}__{inner_stage_id}"
        else:
            data["job_id"] = data["stage_id"] = get_safe_gh_jobname(get_id_or_name(data))
        return data

    def _add_job(self, stage_data):
        stage_id = stage_data.get('stage_id')
        job_id = stage_data.get('job_id')
        self.gh_pipeline_data.register_stage(stage_id=stage_id, job_id=job_id)
        self.gh_pipeline_data.add_job(job_id, self._convert_atlas_stage_to_gh_job(stage_data))

    def _convert_atlas_stage_to_gh_job(self, enriched_stage_data):
        if enriched_stage_data.get('type') not in PipelineConverter._SUPPORTED_JOB_TYPES:
            raise ValueError(f"Only stages of types {PipelineConverter._SUPPORTED_JOB_TYPES} are supported - {enriched_stage_data}")
        github_job = {
            'uses': PipelineConverter._DEFAULT_MODULE_IMAGE_REUSABLE_FLOW,
            'with': {
                'stage_id': enriched_stage_data.get("stage_id"),
                'job_id': enriched_stage_data.get("job_id"),
                'module_image': enriched_stage_data.get("path"),
                'module_command': enriched_stage_data.get("command"),
            }
        }
        # if job_name := enriched_stage_data.get("name"):
        #     github_job["name"] = job_name
        if depends := self.gh_pipeline_data.get_previous_stage_jobs():
            github_job["needs"] = list(depends)
        if input_params := enriched_stage_data.get("input"):
            github_job["with"]["input"] = yaml.safe_dump(input_params, sort_keys=False)
        if output_params := enriched_stage_data.get("output"):
            github_job["with"]["output"] = yaml.safe_dump(output_params, sort_keys=False)
        if report_params := enriched_stage_data.get("report"):
            github_job["with"]["report"] = yaml.safe_dump(report_params, sort_keys=False)
        if when_condition := enriched_stage_data.get("when"):
            github_job["with"]["when"] = yaml.safe_dump(when_condition, sort_keys=False)
        if when_statuses := enriched_stage_data.get("when", {}).get("statuses"):
            if "SUCCESS" in when_statuses and "FAILURE" in when_statuses:
                github_job["if"] = "success() || failure()"
            elif "FAILURE" in when_statuses:
                github_job["if"] = "failure()"
        if enriched_stage_data.get('type') == PipelineConverter._REPORT_TYPE:
            report_params = {'version': 'v1'}
            report_params.update(self.gh_pipeline_data.report_params)
            github_job["with"]["report"] = yaml.safe_dump(report_params, sort_keys=False)
        return github_job

    def add_prepare_env_vars_job(self):
        if not self.gh_pipeline_data.get_all_vars():
            return
        self.gh_pipeline_data.register_stage(stage_id=PipelineConverter._DEFAULT_PREPARE_JOB_ID,
                                             job_id=PipelineConverter._DEFAULT_PREPARE_JOB_ID)
        self.gh_pipeline_data.add_job(
            PipelineConverter._DEFAULT_PREPARE_JOB_ID, yaml.safe_load(dedent("""
                name: Prepare Common Env Vars
                runs-on: ubuntu-latest
                steps:
                  - name: Save ENV VARS to stored_data
                    run: |
                      mkdir -p rt/stored_data/prepare-common-vars/job
                      echo "$GITHUB_COMMON_ENV_VARS" >> rt/stored_data/prepare-common-vars/job/params.yaml
                      echo "name: prepare-common-vars" >> rt/stored_data/prepare-common-vars/stage.yaml
                      echo "previous: []" >> rt/stored_data/prepare-common-vars/stage.yaml
                  - name: Upload files
                    uses: actions/upload-artifact@v4
                    with:
                      name: prepare-common-vars
                      path: rt/stored_data
                """)))

    def add_save_output_job(self):
        if not self.atlas_pipeline_data.get_configuration():
            return
        self.gh_pipeline_data.register_stage(stage_id=PipelineConverter._DEFAULT_SAVE_JOB_ID,
                                             job_id=PipelineConverter._DEFAULT_SAVE_JOB_ID)
        output_cfg = self.atlas_pipeline_data.get_configuration().get('output', {})
        if (files := output_cfg.get('files')) and (params := output_cfg.get('params')) and 'files' not in params:
            params['files'] = files
        save_output_github_job = {
            'uses': PipelineConverter._SAVE_PIPELINE_OUTPUT_REUSABLE_FLOW,
            'needs': list(self.gh_pipeline_data.get_previous_stage_jobs()),
            'if': "success() || failure()",
            'with': {
                'input': yaml.safe_dump(output_cfg, sort_keys=False),
            }
        }
        self.gh_pipeline_data.add_job(PipelineConverter._DEFAULT_SAVE_JOB_ID, save_output_github_job)

    def convert(self):
        self.convert_pipeline_info()
        self.convert_atlas_vars()
        self.convert_atlas_jobs_to_job_templates()
        self.add_prepare_env_vars_job()
        self.convert_atlas_stages_to_jobs()
        self.add_save_output_job()


def process_external_url(url: str):
    if "raw.githubusercontent.com" in url.lower():
        response = requests.get(url)
        if response.status_code == 404:
            headers = {"Authorization": f"token {os.getenv('GH_PRIVATE_READ_TOKEN', '')}"}
            response = requests.get(url, headers=headers)
            if response.status_code == 404:
                raise Exception(f"Invalid URL or access token - {url}")
        return response.text
    else:
        return requests.get(url).text


def main():
    atlas_pipeline_data = AtlasPipelineData()
    atlas_pipeline_data.process_params('\n'.join(_trim_lines(_PIPELINE_VARS)))

    for url in _trim_lines(_PIPELINE_DATA):
        if url.lower().startswith("http"):
            file_content = process_external_url(url)
        else:
            with open(Path(os.getenv('CALLER_REPO_DIR', ''), url)) as fs:
                file_content = fs.read()
        atlas_pipeline_data.process_config(file_content)

    pipeline_converter = PipelineConverter(atlas_pipeline_data)
    pipeline_converter.convert()

    with open('GENERATED_WORKFLOW.yml', 'w') as fs:
        yaml.safe_dump(pipeline_converter.gh_pipeline_data.get_pipeline(), fs, sort_keys=False)


if __name__ == '__main__':
    main()
