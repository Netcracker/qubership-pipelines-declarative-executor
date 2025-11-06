from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ExecutionStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SKIPPED = "SKIPPED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @staticmethod
    def list_from_string(statuses_str: str) -> list[ExecutionStatus]:
        if not statuses_str:
            return []
        statuses = []
        for status_name in (s.strip() for s in statuses_str.split(',')):
            try:
                statuses.append(ExecutionStatus[status_name])
            except KeyError:
                pass
        return statuses


class StageType(StrEnum):
    PYTHON_MODULE = "PYTHON_MODULE"
    SHELL_COMMAND = "SHELL_COMMAND"
    PARALLEL_BLOCK = "PARALLEL_BLOCK"
    ATLAS_PIPELINE_TRIGGER = "ATLAS_PIPELINE_TRIGGER" # aka NESTED_PIPELINE
    REPORT = "REPORT"


COMPLEX_TYPES = [StageType.PARALLEL_BLOCK, StageType.ATLAS_PIPELINE_TRIGGER]


@dataclass
class Stage:
    id: str = None
    uuid: str = None
    name: str = None
    path: str = None
    type: str = None
    command: str = None
    input: dict = None
    output: dict = None
    when: When = field(default_factory=lambda: When())
    nested_parallel_stages: list[Stage] = None

    # Runtime Execution Properties
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    start_time: datetime = None
    finish_time: datetime = None
    exec_dir: Path = None
    evaluated_params: dict = None

    def logged_name(self) -> str:
        return f"\"{self.name}\" (id={self.id}, uuid={self.uuid})"


@dataclass
class When:
    condition: str = None
    statuses: list[ExecutionStatus] = field(default_factory=lambda: [ExecutionStatus.SUCCESS])
