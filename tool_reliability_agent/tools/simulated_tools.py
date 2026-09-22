import time
import random
from models import TaskInput, ToolResult
from tools.base_tool import BaseTool
from config import TOOL_A_SUCCESS_SCHEDULE, TOOL_B_SUCCESS_RATE


class SimulatedToolA(BaseTool):
    tool_id = "tool_a"  # 고정 Tool ID 규칙 준수

    def _get_success_rate(self, task_id: int) -> float:
        for (start, end), rate in TOOL_A_SUCCESS_SCHEDULE.items():
            if start <= task_id <= end:
                return rate
        return 0.95  # 범위 밖이면 기본값

    def run(self, task: TaskInput) -> ToolResult:
        start = time.time()
        rate = self._get_success_rate(task.task_id)
        success = random.random() < rate
        latency = time.time() - start
        return ToolResult(
            task_id=task.task_id,
            tool_name=self.tool_id,
            success=success,
            output=f"result for '{task.query}'" if success else None,
            latency_sec=round(latency, 4),
            error_type=None if success else "simulated_failure",
        )


class SimulatedToolB(BaseTool):
    tool_id = "tool_b"

    def run(self, task: TaskInput) -> ToolResult:
        start = time.time()
        success = random.random() < TOOL_B_SUCCESS_RATE
        latency = time.time() - start
        return ToolResult(
            task_id=task.task_id,
            tool_name=self.tool_id,
            success=success,
            output=f"result for '{task.query}'" if success else None,
            latency_sec=round(latency, 4),
            error_type=None if success else "simulated_failure",
        )