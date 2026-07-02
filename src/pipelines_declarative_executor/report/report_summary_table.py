from datetime import datetime

import tabulate
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import ExecutionStatus, StageType
from pipelines_declarative_executor.utils.color_utils import ColorUtils
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.string_utils import StringUtils


class ReportSummaryTable:

    TABLE_BORDER_LINE_WIDTH = 120
    TABULATE_TABLE_FORMAT = "github"
    UNKNOWN_VALUE = "N/A"

    BLANK_GUIDE = "    "
    NESTED_PIPELINE_TRIGGER_MARKER = "▶ "
    PIPES          = ("│   ", "├─ ", "└─ ")
    PIPES_PARALLEL = ("║   ", "╠═ ", "╚═ ")

    @staticmethod
    def generate_summary_table(generated_report: dict = None, execution: PipelineExecution = None) -> str:
        if generated_report:
            report = generated_report
        elif execution:
            from pipelines_declarative_executor.report.report_collector import ReportCollector
            report = ReportCollector.prepare_ui_view(execution)
        else:
            return "[No data for report provided]"

        all_rows = []
        ReportSummaryTable._transform_stages_to_rows(report.get('stages', []), all_rows)
        return ReportSummaryTable._build_table_with_header(
            report=report,
            rows=all_rows
        )

    @staticmethod
    def _transform_stages_to_rows(stages: list, rows: list, level: int = 0, ancestor_guides: list = None, parent_is_parallel: bool = False) -> None:
        if ancestor_guides is None:
            ancestor_guides = []

        for i, stage in enumerate(stages):
            is_current_last = (i == len(stages) - 1)

            nesting_prefix = ""
            if level > 0:
                if parent_is_parallel:
                    connector = ReportSummaryTable.PIPES_PARALLEL[2] if is_current_last else ReportSummaryTable.PIPES_PARALLEL[1]
                else:
                    connector = ReportSummaryTable.PIPES[2] if is_current_last else ReportSummaryTable.PIPES[1]
                nesting_prefix = "".join(ancestor_guides) + connector

            rows.append({
                'prefix': nesting_prefix,
                'name': ReportSummaryTable._get_or_default(stage, 'name'),
                'id': ReportSummaryTable._get_or_default(stage, 'id'),
                'status': ReportSummaryTable._get_or_default(stage, 'status'),
                'time': ReportSummaryTable._get_precise_duration_str(stage.get('startedAt'), stage.get('finishedAt')),
                'type': ReportSummaryTable._get_or_default(stage, 'type'),
                'command': stage.get('command', ""),
                'level': level,
                'peakMem': stage.get('performance', {}).get('peakMemory'),
                'avgCpu': stage.get('performance', {}).get('avgCpu'),
            })

            if is_current_last:
                my_guide = ReportSummaryTable.BLANK_GUIDE
            else:
                my_guide = ReportSummaryTable.PIPES_PARALLEL[0] if parent_is_parallel else ReportSummaryTable.PIPES[0]
            child_guides = ancestor_guides + [my_guide]

            if parallel_stages := stage.get('parallelStages', []):
                ReportSummaryTable._transform_stages_to_rows(parallel_stages, rows, level + 1, child_guides, parent_is_parallel=True)

            if nested_stages := stage.get('nestedPipeline', {}).get('stages', []):
                ReportSummaryTable._transform_stages_to_rows(nested_stages, rows, level + 1, child_guides, parent_is_parallel=False)

    @staticmethod
    def _build_table_with_header(report: dict, rows: list) -> str:
        headers = ["Stage ID", "Stage Name", "Status", "Duration", "Type", "Command"]
        table_data = []
        for row in rows:
            marker = ReportSummaryTable.NESTED_PIPELINE_TRIGGER_MARKER if row['type'] == StageType.ATLAS_PIPELINE_TRIGGER else ""
            table_data.append([
                row['id'],
                f"{row['prefix']}{marker}{row['name']}",
                row['status'],
                row['time'],
                row['type'],
                row['command'],
            ])

        if EnvVar.ENABLE_STAGE_RESOURCE_USAGE_PROFILING:
            headers.extend(["Peak Mem", "Avg Cpu"])
            for i, row in enumerate(rows):
                table_data[i].extend([row['peakMem'], row['avgCpu']])

        tabulate.PRESERVE_WHITESPACE = True # to keep our stage-name indentation/nesting prefixes
        table_str = tabulate.tabulate(table_data, headers, tablefmt=ReportSummaryTable.TABULATE_TABLE_FORMAT)
        table_str = ReportSummaryTable._colorize_failed_rows(table_str, rows)

        lines = []
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)
        lines.append(table_str)
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)
        lines.append(f"PIPELINE SUMMARY: {ReportSummaryTable._get_or_default(report, 'name')}")
        lines.append(f"ID: {ReportSummaryTable._get_or_default(report, 'id')}")
        lines.append(f"Total Duration: {ReportSummaryTable._get_precise_duration_str(report.get('startedAt'), report.get('finishedAt'))}")
        lines.append(f"Total Stages: {len(rows)}")
        lines.append(f"Retry attempts: {report.get('customData', {}).get('retry_attempt', 0)}")
        lines.append(f"Status: {ColorUtils.colorize_status(ReportSummaryTable._get_or_default(report, 'status'))}")
        if EnvVar.ENABLE_PEAK_RESOURCE_USAGE_PROFILING:
            lines.extend(ReportSummaryTable._build_peak_usage_section())
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)

        return "\n".join(lines)

    @staticmethod
    def _colorize_failed_rows(table_str: str, rows: list) -> str:
        # we colorize whole rows to keep width-related calculations same between file/console representations;
        # data row i is line i + 2 (with 'github' tablefmt);
        table_lines = table_str.split("\n")
        header_offset = 2
        for i, row in enumerate(rows):
            line_idx = header_offset + i
            if row['status'] == ExecutionStatus.FAILED and line_idx < len(table_lines):
                table_lines[line_idx] = ColorUtils.with_color(table_lines[line_idx], ColorUtils.FAILURE_COLOR)
        return "\n".join(table_lines)

    @staticmethod
    def _get_or_default(obj: dict, field: str):
        if field not in obj or obj[field] is None:
            return ReportSummaryTable.UNKNOWN_VALUE
        return obj[field]

    @staticmethod
    def _build_peak_usage_section():
        from pipelines_declarative_executor.executor.resource_manager import ResourceManager
        return [
            f"Peak Memory: {ResourceManager.PEAKS['memory']['value']:.1f} MB (at {ResourceManager.PEAKS['memory']['datetime']})",
            f"Peak CPU: {ResourceManager.PEAKS['cpu']['value']:.1f}% (at {ResourceManager.PEAKS['cpu']['datetime']})",
        ]

    @staticmethod
    def _get_precise_duration_str(start_time: datetime, finish_time: datetime) -> str:
        if not (start_time and finish_time):
            return "N/A"
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(finish_time, str):
            finish_time = datetime.fromisoformat(finish_time)
        duration = StringUtils.get_duration_str(start_time, finish_time)
        seconds = (finish_time - start_time).total_seconds()
        if seconds < 60:
            return f"{duration} ({seconds:.3f}s)"
        else:
            return duration
