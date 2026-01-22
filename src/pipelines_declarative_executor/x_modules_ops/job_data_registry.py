import os, typing, yaml

from pathlib import Path
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.sops_utils import SOPS, SopsUtils
from pipelines_declarative_executor.x_modules_ops.dict_utils import HierarchicalDict

PathRepr: typing.TypeAlias = str | bytes | os.PathLike


class JobDataRegistry:
    _PARAMS_TEMPLATE = {'kind': 'AtlasModuleParamsInsecure', 'apiVersion': 'v1',}
    _PARAMS_SECURE_TEMPLATE = {'kind': 'AtlasModuleParamsSecure', 'apiVersion': 'v1',}
    _CONTEXT_DESCRIPTOR_TEMPLATE = {'kind': 'AtlasModuleContextDescriptor', 'apiVersion': 'v1',}
    _DEFAULT_CONTEXT_PATHS = {
        'paths.logs':                 'logs',
        'paths.temp':                 'temp',
        'paths.input.params':         'input_params.yaml',
        'paths.input.params_secure':  'input_params_secure.yaml',
        'paths.input.files':          'input_files',
        'paths.output.params':        'output_params.yaml',
        'paths.output.params_secure': 'output_params_secure.yaml',
        'paths.output.files':         'output_files',
    }
    _merge_dicts_func = dict.__or__

    @staticmethod
    def _create_context_descriptor(context_paths_root: PathRepr|None=None) -> dict:
        context_descriptor_wrap = HierarchicalDict()
        for k, v in JobDataRegistry._DEFAULT_CONTEXT_PATHS.items():
            context_descriptor_wrap[k] = os.path.join(context_paths_root, v) if context_paths_root else v
        return context_descriptor_wrap.data

    def __init__(self, base: PathRepr, relative_to_context: bool=False):
        if os.path.isfile(base):  # `base` is an existing context file
            self.context_descriptor_filepath = Path(base)
            self.context_descriptor = JobDataRegistry._read_yaml(self.context_descriptor_filepath)
        else:  # `base` is a directory, might not exist: applying default layout
            JobDataRegistry._ensure_dir(base)
            self.context_descriptor_filepath = Path(base, 'context.yaml')
            self.context_descriptor = JobDataRegistry._create_context_descriptor(None if relative_to_context else base)

        context_dirpath = self.context_descriptor_filepath.parent

        context_descriptor_wrap = HierarchicalDict.wrap(self.context_descriptor)
        def _path(param) -> Path:
            if param_value := context_descriptor_wrap.get(param):
                return Path(context_dirpath, param_value) if relative_to_context else Path(param_value)
            return None

        self.input_params_filepath          = _path('paths.input.params')
        self.input_params_secure_filepath   = _path('paths.input.params_secure')
        self.input_files_dirpath: Path      = JobDataRegistry._ensure_dir(_path('paths.input.files'))
        self.output_params_filepath         = _path('paths.output.params')
        self.output_params_secure_filepath  = _path('paths.output.params_secure')
        self.output_files_dirpath: Path     = JobDataRegistry._ensure_dir(_path('paths.output.files'))
        self.logs_dirpath                   = _path('path.logs') or (context_dirpath / 'logs')

    @staticmethod
    def read_descriptor_from_file(file: PathRepr):
        if not (file and os.path.isfile(file)):
            return {}
        with open(file) as fs:
            file_content = fs.read()
        if EnvVar.ENCRYPT_OUTPUT_PARAMS:
            descriptor, _ = SopsUtils.load_and_decrypt_yaml(file_content)
        else:
            descriptor = yaml.safe_load(file_content)
        for k in ('kind', 'apiVersion'):
            descriptor.pop(k, None)
        return descriptor

    def write_context_descriptor(self):
        JobDataRegistry._write_yaml(
                JobDataRegistry._merge_dicts_func(JobDataRegistry._CONTEXT_DESCRIPTOR_TEMPLATE, self.context_descriptor),
                self.context_descriptor_filepath
        )

    def write_input_params(self, params):
        JobDataRegistry._write_params_to_file(params, self.input_params_filepath)

    def write_output_params(self, params):
        JobDataRegistry._write_params_to_file(params, self.output_params_filepath)

    def write_input_params_secure(self, params_secure):
        content_dict = JobDataRegistry._merge_dicts_func(JobDataRegistry._PARAMS_SECURE_TEMPLATE, params_secure)
        JobDataRegistry._write_yaml(content_dict, self.input_params_secure_filepath)

    def write_output_params_secure(self, params_secure):
        content_dict = JobDataRegistry._merge_dicts_func(JobDataRegistry._PARAMS_SECURE_TEMPLATE, params_secure)
        if EnvVar.ENCRYPT_OUTPUT_PARAMS:
            encrypted_content = SOPS.encrypt(yaml.safe_dump(content_dict, sort_keys=False))
            JobDataRegistry._write_file(encrypted_content, self.output_params_secure_filepath)
        else:
            JobDataRegistry._write_yaml(content_dict, self.output_params_secure_filepath)

    @staticmethod
    def _write_params_to_file(params, file: PathRepr):
        JobDataRegistry._write_yaml(
            JobDataRegistry._merge_dicts_func(JobDataRegistry._PARAMS_TEMPLATE, params),
            file
        )

    @staticmethod
    def _ensure_dir(path: PathRepr):
        if path:
            os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _read_yaml(file=None):
        with open(file) as fs:
            return yaml.safe_load(fs)

    @staticmethod
    def _write_yaml(content, file):
        filepath = Path(file)
        if dirpath := filepath.parent:
            dirpath.mkdir(parents=True, exist_ok=True)
        with filepath.open('w') as fs:
            yaml.safe_dump(content, fs, sort_keys=False)

    @staticmethod
    def _write_file(content, file):
        if dirpath := Path(file).parent:
            dirpath.mkdir(parents=True, exist_ok=True)
        with open(file, 'w') as fs:
            fs.write(content)
