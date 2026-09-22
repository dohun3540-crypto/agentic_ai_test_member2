from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class TaskInput:
    task_id: int
    query: str

@dataclass
class ToolResult:
    task_id: int
    tool_name: str
    success: bool
    output: Any
    latency_sec: float
    error_type: Optional[str] = None

@dataclass
class RoutingDecision:
    task_id: int
    selected_tool: str
    reliability_scores: dict
    used_exploration: bool = False