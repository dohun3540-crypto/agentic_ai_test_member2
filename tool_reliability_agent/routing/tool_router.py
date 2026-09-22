"""규격 호환 Baseline 및 Reliability-aware Tool Router."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

import config
from models import RoutingDecision, TaskInput


class ToolRouter(ABC):
    @abstractmethod
    def select_tool(
        self,
        task: TaskInput,
        candidate_tools: list[str],
        reliability_scores: dict[str, float],
    ) -> RoutingDecision:
        raise NotImplementedError


class BaselineRouter(ToolRouter):
    """Reliability를 선택에 사용하지 않는 비교 기준 Router."""

    def __init__(self, preferred_tool: str = config.BASELINE_PREFERRED_TOOL) -> None:
        self.preferred_tool = preferred_tool

    def select_tool(
        self,
        task: TaskInput,
        candidate_tools: list[str],
        reliability_scores: dict[str, float],
    ) -> RoutingDecision:
        tools = _validate_inputs(candidate_tools, reliability_scores, require_scores=False)
        selected_tool = self.preferred_tool if self.preferred_tool in tools else tools[0]
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool=selected_tool,
            reliability_scores=dict(reliability_scores),
            used_exploration=False,
        )


class ReliabilityRouter(ToolRouter):
    """Reliability와 exploration을 함께 사용하는 제안 Router."""

    def __init__(
        self,
        exploration_rate: float = config.EXPLORATION_RATE,
        forced_probe_interval: int = config.FORCED_PROBE_INTERVAL,
        min_switch_gain: float = config.MIN_SWITCH_GAIN,
        random_seed: int = config.RANDOM_SEED,
    ) -> None:
        if not 0.0 <= exploration_rate <= 1.0:
            raise ValueError("exploration_rate must be between 0.0 and 1.0")
        if forced_probe_interval < 0:
            raise ValueError("forced_probe_interval must be non-negative")
        if not 0.0 <= min_switch_gain <= 1.0:
            raise ValueError("min_switch_gain must be between 0.0 and 1.0")
        self.exploration_rate = exploration_rate
        self.forced_probe_interval = forced_probe_interval
        self.min_switch_gain = min_switch_gain
        self.random_seed = random_seed
        self._rng = random.Random(random_seed)
        self._current_tool: str | None = None
        self._last_selected_task: dict[str, int] = {}

    def select_tool(
        self,
        task: TaskInput,
        candidate_tools: list[str],
        reliability_scores: dict[str, float],
    ) -> RoutingDecision:
        tools = _validate_inputs(candidate_tools, reliability_scores, require_scores=True)
        scores = {tool: float(reliability_scores[tool]) for tool in tools}

        overdue_tools = self._get_overdue_tools(task.task_id, tools)
        if overdue_tools:
            selected_tool = min(
                overdue_tools,
                key=lambda tool: self._last_selected_task.get(tool, 0),
            )
            used_exploration = True
        elif len(tools) > 1 and self._rng.random() < self.exploration_rate:
            alternatives = [tool for tool in tools if tool != self._current_tool]
            selected_tool = self._rng.choice(alternatives or tools)
            used_exploration = True
        else:
            best_tool = max(tools, key=lambda tool: scores[tool])
            selected_tool = self._apply_hysteresis(best_tool, tools, scores)
            used_exploration = False

        self._current_tool = selected_tool
        self._last_selected_task[selected_tool] = task.task_id
        return RoutingDecision(
            task_id=task.task_id,
            selected_tool=selected_tool,
            reliability_scores=scores,
            used_exploration=used_exploration,
        )

    def _get_overdue_tools(self, task_id: int, tools: list[str]) -> list[str]:
        if self.forced_probe_interval == 0:
            return []
        return [
            tool
            for tool in tools
            if task_id - self._last_selected_task.get(tool, 0)
            >= self.forced_probe_interval
        ]

    def _apply_hysteresis(
        self,
        best_tool: str,
        tools: list[str],
        reliability_scores: dict[str, float],
    ) -> str:
        if self._current_tool not in tools or self._current_tool == best_tool:
            return best_tool
        current_score = reliability_scores[self._current_tool]
        best_score = reliability_scores[best_tool]
        if best_score - current_score < self.min_switch_gain:
            return self._current_tool
        return best_tool


def _validate_inputs(
    candidate_tools: list[str],
    reliability_scores: dict[str, float],
    require_scores: bool,
) -> list[str]:
    tools = list(dict.fromkeys(candidate_tools))
    if not tools:
        raise ValueError("candidate_tools must contain at least one Tool ID")
    unknown = set(tools) - set(config.TOOL_IDS)
    if unknown:
        raise ValueError(f"Unknown Tool ID: {sorted(unknown)}")
    if require_scores:
        missing = [tool for tool in tools if tool not in reliability_scores]
        if missing:
            raise ValueError(f"Missing Reliability Score: {missing}")
    for tool, score in reliability_scores.items():
        if tool in tools and not 0.0 <= float(score) <= 1.0:
            raise ValueError(f"Reliability Score for {tool} must be in [0.0, 1.0]")
    return tools
