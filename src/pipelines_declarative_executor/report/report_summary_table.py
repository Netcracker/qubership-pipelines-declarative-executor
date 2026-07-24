from datetime import datetime

import tabulate
from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import ExecutionStatus, StageType
from pipelines_declarative_executor.utils.color_utils import ColorUtils
from pipelines_declarative_executor.utils.env_var_utils import EnvVar
from pipelines_declarative_executor.utils.logging_utils import LoggingUtils
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

            row_index = len(rows)
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
                'opens_collapse': False,
                'descendant_count': 0,
            })

            if is_current_last:
                my_guide = ReportSummaryTable.BLANK_GUIDE
            else:
                my_guide = ReportSummaryTable.PIPES_PARALLEL[0] if parent_is_parallel else ReportSummaryTable.PIPES[0]
            child_guides = ancestor_guides + [my_guide]

            children_start = len(rows)
            if parallel_stages := stage.get('parallelStages', []):
                ReportSummaryTable._transform_stages_to_rows(parallel_stages, rows, level + 1, child_guides, parent_is_parallel=True)

            if nested_stages := stage.get('nestedPipeline', {}).get('stages', []):
                ReportSummaryTable._transform_stages_to_rows(nested_stages, rows, level + 1, child_guides, parent_is_parallel=False)

            descendant_count = len(rows) - children_start
            if descendant_count > 0:
                rows[row_index]['opens_collapse'] = True
                rows[row_index]['descendant_count'] = descendant_count

    @staticmethod
    def _collapsible_summary_enabled() -> bool:
        return EnvVar.ENABLE_COLLAPSIBLE_SUMMARY_TABLE_ROWS and EnvVar.IS_GITLAB

    @staticmethod
    def _should_collapse_row(row: dict) -> bool:
        return bool(row.get('opens_collapse'))

    @staticmethod
    def _build_table_with_header(report: dict, rows: list) -> str:
        headers = ["Stage ID", "Stage Name", "Status", "Duration", "Type", "Command"]
        table_data = []
        for row in rows:
            marker = ReportSummaryTable.NESTED_PIPELINE_TRIGGER_MARKER if row['type'] == StageType.ATLAS_PIPELINE_TRIGGER else ""
            table_data.append([
                ReportSummaryTable._format_stage_id(row['id']),
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

        tabulate.PRESERVE_WHITESPACE = True  # to keep our stage-name indentation/nesting prefixes
        table_str = tabulate.tabulate(table_data, headers, tablefmt=ReportSummaryTable.TABULATE_TABLE_FORMAT)
        table_lines = table_str.split("\n")
        header_offset = 2
        header_lines = table_lines[:header_offset]
        data_lines = table_lines[header_offset:]

        if ReportSummaryTable._collapsible_summary_enabled():
            body_lines = ReportSummaryTable._emit_collapsible_data_lines(rows, data_lines)
        else:
            body_lines = ReportSummaryTable._colorize_data_lines(rows, data_lines)

        lines = []
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)
        lines.extend(header_lines)
        lines.extend(body_lines)
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
    def _colorize_line_if_failed(line: str, row: dict) -> str:
        if row['status'] == ExecutionStatus.FAILED:
            return ColorUtils.with_color(line, ColorUtils.FAILURE_COLOR)
        return line

    @staticmethod
    def _colorize_data_lines(rows: list, data_lines: list) -> list:
        colored = []
        for i, row in enumerate(rows):
            if i < len(data_lines):
                colored.append(ReportSummaryTable._colorize_line_if_failed(data_lines[i], row))
        return colored

    @staticmethod
    def _emit_collapsible_data_lines(rows: list, data_lines: list, start: int = 0, end: int = None) -> list:
        if end is None:
            end = len(rows)
        emitted = []
        i = start
        while i < end:
            row = rows[i]
            line = data_lines[i] if i < len(data_lines) else ""
            line = ReportSummaryTable._colorize_line_if_failed(line, row)

            if ReportSummaryTable._should_collapse_row(row):
                section_id = str(row['id'])
                emitted.append(LoggingUtils.ci_section_start(header=line, section_id=section_id))
                desc_start = i + 1
                desc_end = i + 1 + row['descendant_count']
                emitted.extend(ReportSummaryTable._emit_collapsible_data_lines(rows, data_lines, desc_start, desc_end))
                emitted.append(LoggingUtils.ci_section_end(section_id=section_id))
                i = desc_end
            else:
                emitted.append(line)
                i += 1
        return emitted

    @staticmethod
    def _format_stage_id(stage_id: str) -> str:
        if EnvVar.USE_COMPACT_LOGGED_NAMES and stage_id and len(stage_id) > 8:
            return f"{stage_id[:8]}..."
        return stage_id

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
