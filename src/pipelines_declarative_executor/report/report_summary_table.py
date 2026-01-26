from tabulate import tabulate
from pipelines_declarative_executor.model.pipeline import PipelineExecution


class ReportSummaryTable:

    TABLE_BORDER_LINE_WIDTH = 120
    TABULATE_TABLE_FORMAT = "github"
    UNKNOWN_VALUE = "N/A"

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
    def _transform_stages_to_rows(stages: list, rows: list, level: int = 0, ancestors_last_flags: list = None) -> None:
        if ancestors_last_flags is None:
            ancestors_last_flags = []

        for i, stage in enumerate(stages):
            is_current_last = (i == len(stages) - 1)
            child_ancestors_flags = ancestors_last_flags + [is_current_last]

            nesting_prefix = ""
            if level > 0:
                for ancestor_was_last in ancestors_last_flags:
                    nesting_prefix += "│   " if not ancestor_was_last else "    "
                nesting_prefix += "└─ " if is_current_last else "├─ "

            rows.append({
                'prefix': nesting_prefix,
                'name': ReportSummaryTable._get_or_default(stage, 'name'),
                'id': ReportSummaryTable._get_or_default(stage, 'id'),
                'status': ReportSummaryTable._get_or_default(stage, 'status'),
                'time': ReportSummaryTable._get_or_default(stage, 'time'),
                'type': ReportSummaryTable._get_or_default(stage, 'type'),
                'command': stage.get('command', ""),
                'level': level,
            })

            if parallel_stages := stage.get('parallelStages', []):
                ReportSummaryTable._transform_stages_to_rows(parallel_stages, rows, level + 1, child_ancestors_flags)

            if nested_stages := stage.get('nestedPipeline', {}).get('stages', []):
                ReportSummaryTable._transform_stages_to_rows(nested_stages, rows, level + 1, child_ancestors_flags)

    @staticmethod
    def _build_table_with_header(report: dict, rows: list) -> str:
        headers = ["Stage ID", "Stage Name", "Status", "Duration", "Type", "Command"]
        table_data = []
        for row in rows:
            table_data.append([
                row['id'],
                f"{row['prefix']}{row['name']}",
                row['status'],
                row['time'],
                row['type'],
                row['command'],
            ])

        lines = []
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)
        lines.append(f"PIPELINE SUMMARY: {ReportSummaryTable._get_or_default(report, 'name')}")
        lines.append(f"ID: {ReportSummaryTable._get_or_default(report, 'id')}")
        lines.append(f"Total Duration: {ReportSummaryTable._get_or_default(report, 'time')}")
        lines.append(f"Total Stages: {len(rows)}")
        lines.append(f"Status: {ReportSummaryTable._get_or_default(report, 'status')}")
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)
        lines.append(tabulate(table_data, headers, tablefmt=ReportSummaryTable.TABULATE_TABLE_FORMAT))
        lines.append("")
        lines.append("=" * ReportSummaryTable.TABLE_BORDER_LINE_WIDTH)

        return "\n".join(lines)

    @staticmethod
    def _get_or_default(obj: dict, field: str):
        if field not in obj or obj[field] is None:
            return ReportSummaryTable.UNKNOWN_VALUE
        return obj[field]
