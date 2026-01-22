from __future__ import annotations

import asyncio

from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger
from pathlib import Path

from pipelines_declarative_executor.model.stage import Stage, ExecutionStatus
from pipelines_declarative_executor.utils.common_utils import CommonUtils
from pipelines_declarative_executor.utils.constants import Constants
from pipelines_declarative_executor.utils.string_utils import StringUtils


@dataclass
class Pipeline:
    id: str = None
    name: str = None
    stages: list[Stage] = field(default_factory=list)
    configuration: dict = field(default_factory=dict)

    def logged_name(self) -> str:
        return f"\"{self.name}\" (id={self.id})"


@dataclass
class PipelineVars:
    vars_pipeline: dict = field(default_factory=dict)
    vars_config: dict = field(default_factory=dict)
    vars_override: dict = field(default_factory=dict)
    vars_retry: dict = field(default_factory=dict)
    vars_stage_output: dict = field(default_factory=dict)

    files_info: dict = field(default_factory=dict)
    vars_source: dict = field(default_factory=dict)
    secure_vars: set = field(default_factory=set)

    def __post_init__(self):
        self._merged_initial_vars = {}
        self._initial_vars_with_sources = []

    def all_vars(self) -> dict:
        if not self._merged_initial_vars:
            self._merged_initial_vars = {
                **self.vars_pipeline,
                **self.vars_config,
                **self.vars_override,
                **self.vars_retry,
            }
        return {
            **self._merged_initial_vars,
            **self.vars_stage_output
        }

    def calculate_expression(self, exp) -> str:
        return StringUtils.substitute_string(self.all_vars(), expression=exp)

    def initial_vars_with_sources(self) -> list:
        if not self._initial_vars_with_sources:
            for key, value in self._merged_initial_vars.items():
                is_secure = key in self.secure_vars
                self._initial_vars_with_sources.append(CommonUtils.var_with_source(
                    key, Constants.DEFAULT_MASKED_VALUE if is_secure else value,
                    self.vars_source[key]))
        return self._initial_vars_with_sources


@dataclass
class PipelineExecution:
    inputs: dict = None
    pipeline: Pipeline = None
    vars: PipelineVars = None

    # Runtime Execution Properties
    exec_dir: Path = None
    state_dir: Path = None
    output_dir: Path = None
    is_dry_run: bool = False
    exec_process: asyncio.Task = None
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    code: str = None
    start_time: datetime = None
    finish_time: datetime = None
    logger: Logger = None
    is_retry: bool = False
    is_nested: bool = False
    previous_executions: list = field(default_factory=list)

    def store_state(self):
        if not self.state_dir:
            self.state_dir = self.exec_dir.joinpath(Constants.PIPELINE_STATE_DIR_NAME)
        if not self.state_dir.exists():
            self.state_dir.mkdir(parents=True, exist_ok=True)
        CommonUtils.write_json(self._exec_state(), self.state_dir.joinpath(Constants.STATE_EXECUTION_FILE_NAME))
        CommonUtils.write_json(self.pipeline, self.state_dir.joinpath(Constants.STATE_PIPELINE_FILE_NAME))
        CommonUtils.write_json(self.vars, self.state_dir.joinpath(Constants.STATE_VARS_FILE_NAME))

        from pipelines_declarative_executor.report.report_collector import ReportCollector
        CommonUtils.write_json(ReportCollector.prepare_ui_view(self), self.state_dir.joinpath(Constants.PIPELINE_REPORT_FILE_NAME))

    def _exec_state(self) -> dict:
        return {
            "inputs": self.inputs,
            "exec_dir": self.exec_dir,
            "is_dry_run": self.is_dry_run,
            "is_retry": self.is_retry,
            "is_nested": self.is_nested,
            "status": self.status,
            "code": self.code,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
            "previous_executions": self.previous_executions,
        }
