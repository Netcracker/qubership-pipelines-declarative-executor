import shutil
from pathlib import Path

from pipelines_declarative_executor.executor.params_processor import ParamsProcessor
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import Stage, StageType, COMPLEX_TYPES
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.x_modules_ops.dict_utils import HierarchicalDict, UtilsDictionary
from pipelines_declarative_executor.x_modules_ops.job_data_registry import JobDataRegistry


class ContextFilesProcessor:
    @staticmethod
    def prepare_stage_folder(execution: PipelineExecution, stage: Stage, parent_stage: Stage = None):
        is_complex_stage = stage.type in COMPLEX_TYPES
        exec_dir = parent_stage.exec_dir.joinpath(stage.id) if parent_stage else execution.exec_dir.joinpath(stage.id)
        stage.exec_dir = CommonUtils.create_exec_dir(exec_dir, exists_ok=is_complex_stage)
        if is_complex_stage:
            return

        job_data_registry = JobDataRegistry(stage.exec_dir)
        job_data_registry.write_context_descriptor()

        input_calculated = {'params': {}, 'params_secure': {}, 'files': {}}
        input_calculated.update(CommonUtils.calculate_dict_values(execution, stage.input))
        job_data_registry.write_input_params(input_calculated.get('params'))
        job_data_registry.write_input_params_secure(input_calculated.get('params_secure'))

        for file_key, file_path in input_calculated.get('files').items():
            if file_key not in execution.vars.files_info:
                execution.logger.warning(f"Stage {stage.id} requested non-existing file '{file_key}'!")
                continue
            src_path = execution.vars.files_info.get(file_key)
            ContextFilesProcessor._copy_context_files(src_path, file_path, stage.exec_dir)
        stage.evaluated_params['input'] = input_calculated

        if stage.type == StageType.REPORT:
            shutil.copyfile(
                execution.state_dir.joinpath(Constants.PIPELINE_REPORT_FILE_NAME),
                stage.exec_dir.joinpath(Constants.STAGE_INPUT_FILES_DIR_NAME).joinpath(Constants.PIPELINE_REPORT_FOR_REPORT_STAGE_FILE_NAME)
            )

    @staticmethod
    def _copy_context_files(src_path: Path, dst_path: str,
                            dst_context_dir_path: Path,
                            dst_files_folder_name: str = Constants.STAGE_INPUT_FILES_DIR_NAME):
        if src_path.is_dir():
            if dst_path:
                dst_path = dst_context_dir_path.joinpath(dst_files_folder_name).joinpath(dst_path)
            else:
                dst_path = dst_context_dir_path.joinpath(dst_files_folder_name)
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            if dst_path:
                dst_path = dst_context_dir_path.joinpath(dst_files_folder_name).joinpath(dst_path)
            else:
                parts = src_path.parts
                last_index = len(parts) - 1 - parts[::-1].index(Constants.STAGE_OUTPUT_FILES_DIR_NAME)
                dst_path = dst_context_dir_path.joinpath(dst_files_folder_name).joinpath(Path(*parts[last_index + 1:]))
            if dirpath := dst_path.parent:
                dirpath.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src_path, dst_path)

    @staticmethod
    def store_stage_results(execution: PipelineExecution, stage: Stage, stage_dir: Path = None):
        if not stage_dir:
            stage_dir = stage.exec_dir
        job_data_registry = JobDataRegistry(stage_dir)
        output_cfg = CommonUtils.calculate_dict_values(execution, stage.output)

        # STORING PARAMS
        output_params = HierarchicalDict.wrap(JobDataRegistry.read_descriptor_from_file(job_data_registry.output_params_filepath))
        output_params_secure = HierarchicalDict.wrap(JobDataRegistry.read_descriptor_from_file(job_data_registry.output_params_secure_filepath))
        params, params_secure = {}, {}
        for var_name, var_path in output_cfg.get('params', {}).items():
            if var_path == '*':
                if val_map := output_params.get(UtilsDictionary.split_path(var_name)):
                    params.update(val_map)
                if val_map_secure := output_params_secure.get(UtilsDictionary.split_path(var_name)):
                    params_secure.update(val_map_secure)
            elif isinstance(var_path, str):
                if (val := output_params.get(var_path)) is not None:
                    params[var_name] = val
                if (val_secure := output_params_secure.get(var_path)) is not None:
                    params_secure[var_name] = val_secure
            else:
                execution.logger.error(f"Unsupported mapping for output params: {var_name} -> {var_path} (for stage {stage.logged_name()})")
        ParamsProcessor.set_stage_output_vars(execution.vars, params, params_secure, stage.id, stage.uuid)

        # STORING FILE PATHS
        ContextFilesProcessor.store_files_info(output_cfg, execution, stage, stage_dir)
        stage.evaluated_params["output"] = {"params": params, "params_secure": params_secure, "files": output_cfg.get('files', {})}

    @staticmethod
    def store_files_info(output_cfg: dict, execution: PipelineExecution, stage: Stage, stage_dir: Path):
        files_info = {}
        for file_key, file_path in output_cfg.get('files', {}).items():
            if file_path == '*':
                full_file_path = stage_dir.joinpath(Constants.STAGE_OUTPUT_FILES_DIR_NAME)
            else:
                full_file_path = stage_dir.joinpath(Constants.STAGE_OUTPUT_FILES_DIR_NAME).joinpath(file_path)
            if not full_file_path.exists():
                execution.logger.warning(f"Tried to store non-existing path in stage {stage.id}: {file_key} = {full_file_path}")
            else:
                files_info[file_key] = full_file_path
        execution.vars.files_info.update(files_info)

    @staticmethod
    def store_pipeline_results(execution: PipelineExecution):
        execution.output_dir = execution.exec_dir.joinpath(Constants.PIPELINE_OUTPUT_DIR_NAME)
        execution.output_dir.mkdir(parents=True, exist_ok=True)

        output_config = execution.pipeline.configuration.get('output', {})
        if not output_config:
            return

        pipeline_data_registry = JobDataRegistry(execution.output_dir)
        # pipeline_data_registry.write_context_descriptor()  # we don't need 'context.yaml' at this point?

        output_calculated = CommonUtils.calculate_dict_values(execution, output_config)
        pipeline_data_registry.write_output_params(output_calculated.get('params', {}))
        pipeline_data_registry.write_output_params_secure(output_calculated.get('params_secure', {}))

        for file_key, file_path in output_calculated.get('files', {}).items():
            if file_key not in execution.vars.files_info:
                execution.logger.warning(f"Pipeline {execution.pipeline.logged_name()} requested non-existing file \"{file_key}\"!")
                continue
            src_path = execution.vars.files_info.get(file_key)
            ContextFilesProcessor._copy_context_files(src_path, file_path, execution.output_dir, Constants.STAGE_OUTPUT_FILES_DIR_NAME)

    @staticmethod
    def store_retried_stage_results(execution: PipelineExecution, stage: Stage):
        output_params = (stage.evaluated_params or {}).get('output', {})
        params, params_secure = output_params.get('params', {}), output_params.get('params_secure', {})
        ParamsProcessor.set_stage_output_vars(execution.vars, params, params_secure, stage.id, stage.uuid)
        stage_dir = stage.exec_dir if stage.type != StageType.ATLAS_PIPELINE_TRIGGER else stage.exec_dir.joinpath(Constants.PIPELINE_OUTPUT_DIR_NAME)
        ContextFilesProcessor.store_files_info(output_params, execution, stage, stage_dir)
        if stage.type == StageType.PARALLEL_BLOCK and stage.nested_parallel_stages:
            for child_stage in stage.nested_parallel_stages:
                ContextFilesProcessor.store_retried_stage_results(execution, child_stage)
