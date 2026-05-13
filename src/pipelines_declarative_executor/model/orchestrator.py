from dataclasses import dataclass, field


@dataclass
class AtlasMetaFile:
    data: dict
    file_path: str
    is_secure: bool
    is_remote: bool


@dataclass
class PipelineTemplate:
    configuration: dict = field(default_factory=dict)
    job_templates: dict = field(default_factory=dict)
