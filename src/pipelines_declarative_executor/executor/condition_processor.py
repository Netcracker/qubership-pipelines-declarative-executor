from pipelines_declarative_executor.model.pipeline import PipelineExecution
from pipelines_declarative_executor.model.stage import When, ExecutionStatus
from pipelines_declarative_executor.model.exceptions import PipelineExecutorException


class ConditionProcessor:
    @staticmethod
    def need_to_execute(execution: PipelineExecution, when: When) -> bool:
        return ConditionProcessor._check_status(execution, when) and ConditionProcessor._check_condition(execution, when)

    @staticmethod
    def _check_status(execution: PipelineExecution, when: When) -> bool:
        is_any_stage_failed = any(stage.status == ExecutionStatus.FAILED for stage in execution.pipeline.stages)
        return (is_any_stage_failed and ExecutionStatus.FAILED in when.statuses
                or not is_any_stage_failed and ExecutionStatus.SUCCESS in when.statuses)

    @staticmethod
    def _check_condition(execution: PipelineExecution, when: When) -> bool:
        if not when.condition:
            return True
        try:
            condition = execution.vars.calculate_expression(when.condition)
            result = eval(condition, execution.vars.all_vars())
            execution.logger.debug(f"Condition ('{condition}') evaluation result: {result if isinstance(result, bool) else result + ' -> ' + bool(result)}")
            return bool(result)
        except Exception as e:
            execution.logger.error(f"Error during calculation of condition - '{when.condition}' - {e}")
            raise PipelineExecutorException(e)
